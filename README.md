# LiSkill

Reference implementation of **LiSkill**, a term-level license conflict detection
framework for Agent Skill ecosystems — companion artifact of *A Knot in the Stack:
Exploring Open Source License Conflicts in Agent Skill Ecosystems*.

A licence is represented as a set of *(term, attitude)* pairs — 31 terms
(Table 1) × `CAN / CANNOT / MUST` (Table 2) — instead of a licence identifier.
Conflicts are judged on two structures built from that same representation:

* **LST** (License Structure Tree) — Repository / Skill / Component nesting of one
  skill → *intra-skill* cross-level conflicts;
* **SCC** (Skill Composition Chain) — activation order across several skills →
  *inter-skill* composition conflicts.

Both are judged edge by edge with the single compatibility matrix of Table 8, so
inheritance and chain propagation share one semantics.

## Quick start

The **demo path** needs Python 3.9+ and nothing else — no GPU, no database, no API
key. It runs the whole pipeline offline on the bundled sample payloads:

```bash
python -m liskill.cli demo     # end-to-end demo, writes out/report.md
python -m pytest -q            # 91 tests (needs pytest, e.g. pip install pytest)
```

The paper's full run is a different pipeline: the 825,784-skill collection is
stored in MongoDB (`collect --sink mongo`), and the licence understanding model is
LoRA-fine-tuned and served on a GPU (`train`, then `--use-llm` on `termdb`,
`extract`, `dataset` or `detect`). Both paths are wired; only the demo one is
self-contained. See [Models and data](#models-and-data).

`demo` collects the bundled payloads of the 17 markets, cleans them, generates a
calibrated synthetic skill corpus as real packages on disk, extracts the three
declaration levels, builds the term database, runs both detectors and renders a
report:

```
out/report.md           # RQ1 coverage, RQ3 conflicts, walkthrough
out/skills/             # the generated skill packages that were parsed
out/understanding/      # train/dev/test JSONL of the understanding task
```

`liskill termdb --out out/termdb.json` writes Λ(l) separately, for every licence in
the reference set.

Every figure in `out/report.md` is a demo-sample estimate: the report opens with a
**DEMO DATA** banner and each section repeats its demo sample size next to the
paper's figure, so the two scales cannot be confused.

Individual stages:

```bash
python -m liskill.cli collect --offline --sink jsonl --out out/raw.jsonl
python -m liskill.cli spdx --out data/spdx_licenses      # crawl spdx.org licence texts
python -m liskill.cli reference --spdx-dir data/spdx_licenses --out out/licenses.json
python -m liskill.cli termdb --show MIT GPL-3.0-only
python -m liskill.cli dataset --sample 1200
python -m liskill.cli extract examples/skills/frontend-design --repo-license Apache-2.0
python -m liskill.cli detect --intra-only
```

## Repository structure

```
LiSkill-2026/
├── liskill/                    # the framework (§3)
│   ├── ontology.py             # 31 terms x CAN/CANNOT/MUST, modality cues (Tables 1-2, 7)
│   ├── schema.py               # dataset / licence / normalized-record schemas (Tables 4-6)
│   ├── pipeline.py             # stage orchestration behind the CLI
│   ├── report.py               # markdown report renderer
│   ├── cli.py                  # `python -m liskill.cli <stage>`
│   ├── llm.py                  # optional OpenAI-compatible client (Qwen3.5-9B)
│   ├── data_collection_preprocessing/   # §3.1  data acquisition and preprocessing
│   │   ├── skills/              #   §3.1.1  skill harvesting from the 17 markets
│   │   │   ├── platforms.py     #     declarative market definitions (Table 3)
│   │   │   ├── spiders.py       #     list / detail payload parsers
│   │   │   ├── runner.py        #     crawl loop, keyword scan, detail fetch
│   │   │   ├── http.py          #     retry, backoff, rate limiting
│   │   │   ├── clean.py         #     two-stage cleaning, SHA-256 dedup
│   │   │   ├── enrich.py        #     repo licence + package archive (Table 4 anchors)
│   │   │   ├── sink.py          #     JSONL / memory / MongoDB sinks + cursors
│   │   │   └── fixtures.py      #     offline sample payloads for the 17 markets
│   │   └── licenses/            #   §3.1.2  licence reference set
│   │       ├── reference.py     #     four-source merge, alias index, custom LIC-XXXX
│   │       ├── spdx.py          #     spdx.org text crawler (`liskill spdx`)
│   │       └── legal_texts.py   #     bundled term-level corpus
│   ├── extract/                # §3.2  three-level declaration extraction
│   │   ├── layers.py           #   Repository / Skill / Component
│   │   ├── frontmatter.py      #   SKILL.md frontmatter parsing
│   │   ├── normalize.py        #   Appendix-A normalisation, evidence backfill
│   │   └── prompts.py          #   Appendix-A prompt
│   ├── understand/             # §3.3  licence understanding
│   │   ├── reader.py           #   eq. (1): heuristic and LLM readers
│   │   ├── dataset.py          #   eq. (2) dedup, 7:1:2 split
│   │   ├── embedding.py        #   Qwen3-Embedding-0.6B encoder (eq. 2)
│   │   ├── prompt.py           #   Appendix-B prompt
│   │   └── train_lora.py       #   LoRA SFT of Qwen3.5-9B
│   ├── conflict/               # §3.4  conflict detection
│   │   ├── termdb.py           #   term database (eq. 6-8)
│   │   ├── matrix.py           #   Table 8 matrix, edge judgement (eq. 9-10)
│   │   ├── lst.py              #   intra-skill cross-level detection
│   │   └── scc.py              #   composition chain, propagation (eq. 11-12)
│   ├── eval/                   # §4.1.3  metrics
│   │   ├── metrics.py          #   two-level P/R/F1, #Report, FPR, FNR (eq. 13-15)
│   │   └── rq.py               #   RQ1 / RQ3 aggregation
│   └── demo/                   # offline demo + the §4.4.2 workflow generators
│       ├── corpus.py           #   calibrated synthetic skill corpus
│       ├── workflows.py        #   §4.4.2 chains: model-driven + offline generator
│       └── run.py              #   end-to-end runner
├── data/
│   ├── agent_skills/
│   │   └── skills_demo.jsonl   # Table 3: 1,484-skill sample of the collection
│   ├── spdx_licenses/          # §3.1.2: licences.json, texts.jsonl
│   └── license_term_attitude/  # §3.3: annotated train / valid / test split
├── examples/skills/            # Figure 2's example skill + three other declaration shapes
├── tests/                      # 91 tests: ontology, extraction, matrix, detectors, metrics, collectors
├── docs/design.md              # every equation and table → the function implementing it
├── scripts/demo.sh             # thin wrapper around `liskill demo`
├── pyproject.toml
├── README.md
└── LICENSE
```

## Paper ↔ code

| paper | code |
| --- | --- |
| Table 1/2 ontology | `liskill/ontology.py::TERMS`, `ATTITUDES` |
| Table 4 dataset schema | `liskill/schema.py::SkillRecord` |
| Table 5 reference entry | `schema.py::LicenseEntry`, `data_collection_preprocessing/licenses/reference.py::ReferenceSet` |
| Table 6 normalized record | `schema.py::NormalizedRecord`, `extract/normalize.py` |
| Table 7 aggregation and defaults | `conflict/termdb.py::_complete`, `_detect_grant` |
| Table 8 compatibility matrix | `conflict/matrix.py::COMPATIBILITY_MATRIX`, `judge_term` |
| eq. (1) sentence reader | `understand/reader.py` |
| eq. (2) sentence dedup | `understand/dataset.py::dedupe_sentences`, `understand/embedding.py` |
| eq. (6)(7)(8) term database | `conflict/termdb.py` |
| eq. (9)(10) edge judgement | `conflict/matrix.py::edge_conflicts` |
| eq. (11)(12) composition chain | `conflict/scc.py::SkillCompositionChain`, `detect` |
| eq. (13)(14)(15) metrics | `eval/metrics.py` |
| Appendix A / B prompts | `extract/prompts.py`, `understand/prompt.py` |

## Models and data

The demo runs on the deterministic path; the model paths of the paper are one
flag away, and they are *four different* models:

| stage | model | how |
| --- | --- | --- |
| §3.3.3 reading, §3.4.1 term database Λ(l) | Qwen3.5-9B **+ LoRA adapter**, local | `LISKILL_LLM_*` |
| §3.2.2 declaration normalisation | Qwen3.5-9B **base**, local | `LISKILL_NORMALIZE_*` |
| eq. (2) sentence dedup | Qwen3-Embedding-0.6B | `--use-embedding`, `pip install 'liskill[embed]'` |
| §3.3.2 pre-annotation, §4.4.2 workflow generation | DeepSeek-V4-Flash-0731, official API | `LISKILL_DRAFT_*` |

```bash
pip install 'liskill[train]'
python -m liskill.cli train --train out/understanding/train.jsonl --dev out/understanding/dev.jsonl
#  -> adapter written to out/qwen3.5-9b-liskill-lora

# one local server exposes both names: the base model and the adapter
vllm serve Qwen/Qwen3.5-9B --enable-lora \
    --lora-modules Qwen3.5-9B-LiSkill=out/qwen3.5-9b-liskill-lora

export LISKILL_LLM_BASE_URL=http://127.0.0.1:8000/v1
export LISKILL_LLM_MODEL=Qwen3.5-9B-LiSkill    # the adapter, not the base checkpoint
export LISKILL_DRAFT_API_KEY=...               # DeepSeek-V4-Flash-0731

python -m liskill.cli termdb  --use-llm       # §3.4.1 Λ(l): the fine-tuned reader
python -m liskill.cli extract path/to/skill --use-llm   # §3.2.2: the base model
python -m liskill.cli dataset --use-llm       # §3.3.2 labels: drafted by Flash-0731
python -m liskill.cli dataset --use-embedding # eq. (2): Qwen3-Embedding-0.6B dedup
python -m liskill.cli detect  --use-llm       # §4.4.2: chains composed by Flash-0731

pip install 'liskill[store]'                  # full-scale storage
python -m liskill.cli collect --sink mongo --mongo-uri mongodb://localhost:27017
```

Without `--use-embedding`, eq. (2) de-duplication falls back to the dependency-free
character n-gram encoder, which groups the same near-duplicates but is not the
paper's measurement. The encoder loads its weights on first use, so neither the
demo nor the test suite downloads anything.

Without `--use-llm`, `detect` draws its workflows from the seeded offline
generator in `demo/workflows.py`, which follows the same requirement → recall →
minimal-set shape as §4.4.2 but never calls a model; `LLMWorkflowGenerator` in
the same module is the model-driven path.

`data_collection_preprocessing/skills/enrich.py` fills the two physical anchors
of Table 4 — `repo_license` from the GitHub API and the skill package archive —
which are what the Repository and Component levels read.

`data/agent_skills/skills_demo.jsonl` ships the scraped records verbatim; the one
mail credential that a publisher had left inside its own skill text is redacted.

## License

MIT — see [LICENSE](LICENSE).
