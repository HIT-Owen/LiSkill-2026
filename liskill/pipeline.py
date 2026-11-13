"""End-to-end orchestration of the four modules.

    artifacts --extract--> SkillLicenseDoc --termdb--> Λ(l)
              --LST--> intra-skill conflicts
              --SCC--> inter-skill conflicts

The pipeline is deliberately thin: every step is a module call, so a reader can
follow the paper section by section inside this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .conflict.lst import IntraConflict, detect_intra
from .conflict.scc import InterConflict, SkillCompositionChain, WorkflowResult, detect_inter
from .conflict.termdb import TermDatabase
from .extract.layers import SkillArtifact, extract_skill
from .extract.normalize import DeclarationNormalizer
from .data_collection_preprocessing.licenses.reference import ReferenceSet, build_reference_set
from .schema import SkillLicenseDoc


@dataclass
class PipelineResult:
    docs: List[SkillLicenseDoc] = field(default_factory=list)
    intra: List[IntraConflict] = field(default_factory=list)
    inter: List[WorkflowResult] = field(default_factory=list)
    termdb: Optional[TermDatabase] = None

    def docs_by_id(self) -> Dict[str, SkillLicenseDoc]:
        return {doc.skill_id: doc for doc in self.docs}

    @property
    def conflicting_skills(self) -> List[str]:
        seen: List[str] = []
        for conflict in self.intra:
            if conflict.skill_id not in seen:
                seen.append(conflict.skill_id)
        return seen

    @property
    def conflicting_workflows(self) -> List[str]:
        return [result.workflow_id for result in self.inter if result.is_conflict]


class LiSkillPipeline:
    """§3.2 extraction -> §3.3/§3.4.1 term database -> §3.4.2/§3.4.3 detection."""

    def __init__(
        self,
        reference: Optional[ReferenceSet] = None,
        llm=None,
        terms: Optional[Sequence[str]] = None,
    ) -> None:
        self.reference = reference or build_reference_set()
        self.normalizer = DeclarationNormalizer(self.reference, llm=llm)
        self.llm = llm
        self.terms = list(terms) if terms else None
        self._termdb: Optional[TermDatabase] = None

    # ------------------------------------------------------------------ §3.2
    def extract(self, artifacts: Iterable[SkillArtifact]) -> List[SkillLicenseDoc]:
        return [extract_skill(artifact, self.normalizer) for artifact in artifacts]

    # --------------------------------------------------------- §3.3 / §3.4.1
    def build_termdb(self, force: bool = False) -> TermDatabase:
        if self._termdb is None or force:
            # §3.4.1: the observations behind Λ(l) come from the understanding
            # model of §3.3.3 when a client is supplied, and from the offline
            # heuristic reader otherwise.
            reader = None
            if self.llm is not None:
                from .understand.reader import LLMLicenseReader

                reader = LLMLicenseReader(self.llm)
            self._termdb = TermDatabase(self.reference, reader=reader).build()
        return self._termdb

    @property
    def termdb(self) -> TermDatabase:
        return self.build_termdb()

    # --------------------------------------------------------------- §3.4.2
    def detect_intra(self, docs: Sequence[SkillLicenseDoc]) -> List[IntraConflict]:
        return detect_intra(docs, self.termdb, self.terms)

    # --------------------------------------------------------------- §3.4.3
    def detect_inter(
        self,
        chains: Sequence[SkillCompositionChain],
        docs: Sequence[SkillLicenseDoc],
    ) -> List[WorkflowResult]:
        return detect_inter(chains, {doc.skill_id: doc for doc in docs}, self.termdb, self.terms)

    # ------------------------------------------------------------------ entry
    def run(
        self,
        artifacts: Sequence[SkillArtifact],
        chains: Optional[Sequence[SkillCompositionChain]] = None,
    ) -> PipelineResult:
        docs = self.extract(artifacts)
        result = PipelineResult(docs=docs, termdb=self.build_termdb())
        result.intra = self.detect_intra(docs)
        if chains:
            result.inter = self.detect_inter(chains, docs)
        return result

    # ------------------------------------------------------------------ IO
    def save_documents(self, docs: Sequence[SkillLicenseDoc], path: str | Path) -> Path:
        import json

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [doc.to_dict() for doc in docs]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
