"""Sentence-level term–attitude reader (paper §3.3, eq. (1)).

Two interchangeable implementations of :class:`LicenseReader`:

``LLMLicenseReader``
    the real path — prompts the LoRA-fine-tuned Qwen3.5-9B (or any OpenAI
    compatible endpoint) with the template of Appendix B and parses the JSON
    answer.  Used for §3.4.1 when the adapter is available.

``HeuristicLicenseReader``
    the offline path — a deterministic reader driven by the term lexicon in
    :mod:`liskill.ontology`, the modality cues of Table 2 and the term-class
    scoping described in §3.4.2.  It lets the whole pipeline run without a GPU,
    which is what the released demo uses.

Both return the same structure, so the term database and the detectors do not
care which one produced the observations.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from ..ontology import (
    RE_CAN,
    RE_CANNOT,
    RE_CONDITION_MARKER,
    RE_CONDITIONAL_PROHIBITION,
    RE_CLAUSE_SPLIT,
    RE_MUST,
    RE_TERM_CANNOT,
    TERMS,
    ATTITUDE_RANK,
    Term,
    is_obligation,
)
from ..schema import TermAttitude

RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


# --------------------------------------------------------------------------- #
# segmentation
# --------------------------------------------------------------------------- #
def split_sentences(text: str) -> List[str]:
    """Sentence segmentation used by §3.3.2 (NLTK `sent_tokenize` upstream)."""
    out: List[str] = []
    for block in (text or "").replace("\r", "").split("\n"):
        block = block.strip()
        if not block:
            continue
        for sent in RE_SENTENCE_SPLIT.split(block):
            sent = sent.strip()
            if sent:
                out.append(sent)
    return out


def split_clauses(sentence: str) -> List[str]:
    """Split a sentence into clauses on ``;`` / ``:`` / contrastive connectors.

    Conditions and modalities are scoped per clause, which is what keeps
    "you may copy ... provided that you keep the notice" from turning the copy
    permission itself into an obligation.
    """
    parts = [p.strip() for p in RE_CLAUSE_SPLIT.split(sentence) if p and p.strip()]
    return parts or [sentence]


# --------------------------------------------------------------------------- #
# reader interface
# --------------------------------------------------------------------------- #
class LicenseReader(Protocol):
    def read_sentence(self, sentence: str) -> List[TermAttitude]: ...

    def read_text(self, text: str) -> List[TermAttitude]: ...


# --------------------------------------------------------------------------- #
# offline reader
# --------------------------------------------------------------------------- #
class HeuristicLicenseReader:
    """Deterministic term–attitude reader (offline path of §3.3.3)."""

    def __init__(self, terms: Sequence[Term] = TERMS) -> None:
        self._terms = [(t, t.compiled(), t.compiled_guards()) for t in terms]

    # ---------------------------------------------------------------- internals
    @staticmethod
    def _first_meaningful_match(patterns, text: str):
        for pattern in patterns:
            m = pattern.search(text)
            if m:
                return m
        return None

    def _term_matches(self, clause: str) -> List[Tuple[Term, re.Match]]:
        found: List[Tuple[Term, re.Match]] = []
        for term, patterns, guards in self._terms:
            if any(g.search(clause) for g in guards):
                continue
            m = self._first_meaningful_match(patterns, clause)
            if m:
                found.append((term, m))
        return found

    @staticmethod
    def _attitude(term: Term, clause: str, pos: int, cond_pos: Optional[int]) -> Optional[str]:
        term_cannot = RE_TERM_CANNOT.get(term.tid)
        if term_cannot is not None and term_cannot.search(clause):
            return "CANNOT"
        conditional_prohibition = bool(RE_CONDITIONAL_PROHIBITION.search(clause))
        has_cannot = bool(RE_CANNOT.search(clause))
        has_must = bool(RE_MUST.search(clause))
        has_can = bool(RE_CAN.search(clause))

        # R6: "may not ... without prior written permission" is a condition, not a ban
        if conditional_prohibition:
            return "MUST"
        if has_cannot:
            return "CANNOT"
        if has_must:
            # a right that is granted *before* the condition keeps the CAN reading
            if not is_obligation(term.tid) and cond_pos is not None and pos < cond_pos:
                return "CAN"
            return "MUST"
        if has_can:
            return "CAN"
        # R7: the clause addresses no term we can vouch for
        return None

    @staticmethod
    def _evidence(clause: str, start: int, end: int) -> str:
        left = max(0, start - 60)
        right = min(len(clause), end + 100)
        return clause[left:right].strip()

    # ---------------------------------------------------------------- public API
    def read_sentence(self, sentence: str) -> List[TermAttitude]:
        best: Dict[str, TermAttitude] = {}
        for clause in split_clauses(sentence):
            cond_match = RE_CONDITION_MARKER.search(clause)
            cond_pos = cond_match.start() if cond_match else None
            for term, match in self._term_matches(clause):
                attitude = self._attitude(term, clause, match.start(), cond_pos)
                if attitude is None:
                    continue
                previous = best.get(term.tid)
                if previous is None or ATTITUDE_RANK[attitude] > ATTITUDE_RANK[previous.attitude]:
                    best[term.tid] = TermAttitude(
                        term_id=term.tid,
                        attitude=attitude,
                        evidence=self._evidence(clause, match.start(), match.end()),
                    )
        return [best[tid] for tid in sorted(best, key=lambda t: int(t[1:]))]

    def read_text(self, text: str) -> List[TermAttitude]:
        best: Dict[str, TermAttitude] = {}
        for sentence in split_sentences(text):
            for ta in self.read_sentence(sentence):
                previous = best.get(ta.term_id)
                if previous is None or ATTITUDE_RANK[ta.attitude] > ATTITUDE_RANK[previous.attitude]:
                    best[ta.term_id] = ta
        return [best[tid] for tid in sorted(best, key=lambda t: int(t[1:]))]

    def observe(self, text: str) -> Dict[str, List[str]]:
        """Sentence-level observation sets O_l(t) of eq. (6)."""
        observations: Dict[str, List[str]] = {}
        for sentence in split_sentences(text):
            for ta in self.read_sentence(sentence):
                observations.setdefault(ta.term_id, []).append(ta.attitude)
        return observations


# --------------------------------------------------------------------------- #
# model-backed reader
# --------------------------------------------------------------------------- #
class LLMLicenseReader:
    """Prompts the fine-tuned model with the Appendix-B template."""

    def __init__(self, client, prompt_builder=None) -> None:
        from .prompt import build_sentence_prompt  # local import: optional path

        self._client = client
        self._build_prompt = prompt_builder or build_sentence_prompt

    def read_sentence(self, sentence: str) -> List[TermAttitude]:
        raw = self._client.complete(self._build_prompt(sentence), json_mode=True)
        return parse_term_attitudes(raw, sentence)

    def read_text(self, text: str) -> List[TermAttitude]:
        best: Dict[str, TermAttitude] = {}
        for sentence in split_sentences(text):
            for ta in self.read_sentence(sentence):
                previous = best.get(ta.term_id)
                if previous is None or ATTITUDE_RANK[ta.attitude] > ATTITUDE_RANK[previous.attitude]:
                    best[ta.term_id] = ta
        return [best[tid] for tid in sorted(best, key=lambda t: int(t[1:]))]


def parse_term_attitudes(raw: str, sentence: str = "") -> List[TermAttitude]:
    """Parse the model answer ``{"terms": [{"term_id": .., "attitude": ..}]}``."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []
    items = data.get("terms", data if isinstance(data, list) else [])
    out: List[TermAttitude] = []
    known = {t.tid for t in TERMS}
    for item in items:
        tid = str(item.get("term_id", "")).strip().upper()
        attitude = str(item.get("attitude", "")).strip().upper()
        if tid not in known or attitude not in ATTITUDE_RANK:
            continue
        evidence = str(item.get("evidence", ""))
        # R3: evidence must be a verbatim substring of the sentence
        if sentence and evidence and evidence not in sentence:
            evidence = ""
        out.append(TermAttitude(term_id=tid, attitude=attitude, evidence=evidence))
    return out
