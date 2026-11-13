"""Prompt of Appendix B — sentence-level term–attitude extraction.

Four parts, identical for training and inference to avoid template drift
(§3.3.3): the 31 term definitions of Table 1, the three attitudes of Table 2,
seven output constraints and five worked examples.
"""

from __future__ import annotations

import json
from typing import Sequence

from ..ontology import TERMS

SYSTEM = """You are an expert in open-source license analysis. You read one sentence from a
license text and extract every license term that the sentence addresses, together
with the legal attitude the licensor takes towards that term. Return one JSON
object and nothing else.

### TERM ONTOLOGY
Each term denotes a neutral action and carries no permission or prohibition by
itself. Only the 31 terms below are valid.

{ontology}

### LEGAL ATTITUDES
CAN     The licensee may perform the term without any further condition.
CANNOT  The licensee is prohibited from performing the term, with no exception.
MUST    The licensee may perform the term only if the stated condition is met;
        if the condition fails, the term is not permitted.

### RULES
R1. "term_id" MUST be one of T1-T31. Never invent a term.
R2. "attitude" MUST be one of CAN, CANNOT, MUST.
R3. "evidence" MUST be a verbatim substring of the input sentence.
R4. Report each addressed term at most once.
R5. Judge only what the sentence itself states. Do not infer terms that the
    sentence does not address.
R6. A conditional prohibition is MUST, not CANNOT: "may not ... without prior
    written permission" permits the act once the condition is satisfied.
R7. If the sentence addresses no term (titles, definitions, governing law,
    severability), return {{"terms": []}}. Do not force a match.
"""

EXAMPLES = [
    (
        "Permission is hereby granted, free of charge, to any person obtaining a copy of "
        "this software, to deal in the Software without restriction.",
        {"terms": [
            {"term_id": "T1", "attitude": "CAN", "evidence": "copy"},
            {"term_id": "T3", "attitude": "CAN", "evidence": "deal in the Software"},
        ]},
    ),
    (
        "You may not use the material for commercial purposes.",
        {"terms": [
            {"term_id": "T5", "attitude": "CANNOT", "evidence": "for commercial purposes"},
        ]},
    ),
    (
        "You must license the entire work, as a whole, under this License to anyone who "
        "comes into possession of a copy.",
        {"terms": [
            {"term_id": "T31", "attitude": "MUST", "evidence": "under this License"},
        ]},
    ),
    (
        "Neither the name of the copyright holder may be used to endorse or promote "
        "products derived from this software without specific prior written permission.",
        {"terms": [
            {"term_id": "T11", "attitude": "MUST",
             "evidence": "without specific prior written permission"},
        ]},
    ),
    (
        "This License shall be governed by the laws of the State of California.",
        {"terms": []},
    ),
]


def ontology_block() -> str:
    return "\n".join(
        f"  {term.tid:<3s} {term.name:<24s} {term.definition}" for term in TERMS
    )


def build_sentence_prompt(sentence: str) -> str:
    """Render the Appendix-B user prompt for one sentence."""
    examples = "\n".join(
        f'Sentence: "{text}"\nAnswer: {json.dumps(answer, ensure_ascii=False)}'
        for text, answer in EXAMPLES
    )
    return f"""Sentence: "{sentence}"

### EXAMPLES
{examples}

Return one JSON object of the form {{"terms": [{{"term_id": "T5", "attitude": "CANNOT", "evidence": "..."}}]}}.
"""


def build_system_prompt() -> str:
    return SYSTEM.format(ontology=ontology_block())


def build_training_pair(sentence: str, answer: Sequence[dict]) -> dict:
    """One supervised fine-tuning example (prompt -> serialized JSON target)."""
    return {
        "prompt": build_sentence_prompt(sentence),
        "completion": json.dumps({"terms": list(answer)}, ensure_ascii=False),
    }
