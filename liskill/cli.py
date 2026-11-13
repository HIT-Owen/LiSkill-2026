"""Command line entry point.

    python -m liskill.cli demo                     # end-to-end demo, offline
    python -m liskill.cli collect --offline        # parse the bundled payloads
    python -m liskill.cli collect --platforms clawhub skills.lc
    python -m liskill.cli spdx                      # crawl spdx.org license texts
    python -m liskill.cli reference --out out/licenses.json
    python -m liskill.cli termdb --out out/termdb.json
    python -m liskill.cli dataset --sample 500 --out out/understanding
    python -m liskill.cli detect --intra-only
    python -m liskill.cli extract examples/skills/frontend-design
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .data_collection_preprocessing.skills.platforms import platform_names
from .data_collection_preprocessing.skills.runner import Collector
from .data_collection_preprocessing.skills.sink import JsonlSink, MemorySink, MongoSink
from .demo.run import load_example_artifacts, run_demo
from .extract.layers import SkillArtifact
from .data_collection_preprocessing.licenses.reference import build_reference_set
from .pipeline import LiSkillPipeline
from .understand.dataset import build_dataset
from .understand.reader import HeuristicLicenseReader


def _load_llm(args, config_name: str = "from_env"):
    """Client for the model that owns this stage (§4.1.4); ``None`` keeps it offline.

    ``config_name`` selects the constructor, so a stage can never borrow the
    wrong model: ``from_env`` is the fine-tuned reader, ``for_normalization`` is
    the local base Qwen3.5-9B, and ``for_drafting`` is DeepSeek-V4-Flash-0731.
    """
    if not getattr(args, "use_llm", False):
        return None
    from .llm import LLMConfig, OpenAICompatClient

    return OpenAICompatClient(getattr(LLMConfig, config_name)())


def _load_encoder(args):
    """Qwen3-Embedding-0.6B for eq. (2) when ``--use-embedding`` is set.

    Construction is free — the weights load on the first ``encode_*`` call — so
    this never triggers a download while arguments are parsed.
    """
    if not getattr(args, "use_embedding", False):
        return None
    from .understand.embedding import QwenEmbeddingEncoder

    return QwenEmbeddingEncoder()


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_demo(args: argparse.Namespace) -> int:
    outcome = run_demo(
        size=args.size,
        workflows=args.workflows,
        seed=args.seed,
        out_dir=args.out,
        collect=not args.no_collect,
        understanding_sample=args.understanding_sample,
        quiet=args.quiet,
    )
    print("\n=== summary ===")
    for key, value in outcome.summary.items():
        print(f"  {key}: {value}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    if args.sink == "jsonl" and not args.out:
        print("--out is required with --sink jsonl", file=sys.stderr)
        return 2
    sink = {
        "jsonl": lambda: JsonlSink(args.out),
        "memory": MemorySink,
        "mongo": lambda: MongoSink(uri=args.mongo_uri, db_name=args.db, col_name=args.collection),
    }[args.sink]()
    collector = Collector(sink=sink, offline=args.offline)
    report = collector.run(args.platforms, max_pages=args.max_pages)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_spdx(args: argparse.Namespace) -> int:
    from .data_collection_preprocessing.licenses.spdx import crawl

    stats = crawl(
        args.out,
        limit=args.limit,
        with_template=args.with_template,
        refresh=args.refresh,
        requests_per_second=args.rate,
    )
    print(json.dumps(stats.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_reference(args: argparse.Namespace) -> int:
    if args.spdx_dir:
        from .data_collection_preprocessing.licenses.spdx import build_reference_set as build_from_spdx

        reference = build_from_spdx(args.spdx_dir)
        if args.include_custom:
            from .data_collection_preprocessing.licenses.legal_texts import CUSTOM_TEXTS

            for name, clauses in CUSTOM_TEXTS.items():
                reference.register_custom(name, "\n".join(clauses))
    else:
        reference = build_reference_set(include_custom=args.include_custom)
    out = Path(args.out or "out/licenses.json")
    reference.save(out)
    print(
        f"{len(reference.entries)} licenses "
        f"({reference.standard_count} standard, {reference.custom_count} custom) -> {out}"
    )
    return 0


def cmd_termdb(args: argparse.Namespace) -> int:
    pipeline = LiSkillPipeline(llm=_load_llm(args))
    termdb = pipeline.build_termdb()
    out = Path(args.out or "out/termdb.json")
    termdb.save(out)
    print(f"{len(termdb.profiles)} license profiles -> {out}")
    for license_id in args.show or ("MIT", "GPL-3.0-only"):
        if termdb.is_known(license_id):
            print(f"  {license_id}: {termdb.summary(license_id)}")
    return 0


def cmd_dataset(args: argparse.Namespace) -> int:
    pipeline = LiSkillPipeline()
    # §3.3.2 stage 1 is drafted by the general model, never by the §3.3.3 reader
    reader = HeuristicLicenseReader() if not getattr(args, "use_llm", False) else None
    if reader is None:
        from .understand.reader import LLMLicenseReader

        reader = LLMLicenseReader(_load_llm(args, "for_drafting"))
    texts = {
        license_id: entry.license_text
        for license_id, entry in pipeline.reference.entries.items()
        if entry.license_text
    }
    result = build_dataset(
        texts,
        reader,
        sample_size=args.sample,
        out_dir=args.out or "out/understanding",
        # eq. (2): the paper's Qwen3-Embedding-0.6B, or the offline n-gram stand-in
        encoder=_load_encoder(args),
    )
    print(json.dumps({k: v for k, v in result.items() if k != "samples"}, indent=2))
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    skill_dir = Path(args.path)
    skill_md = skill_dir / "SKILL.md"
    artifact = SkillArtifact(
        skill_id=skill_dir.name,
        name=skill_dir.name,
        skill_md_content=skill_md.read_text(encoding="utf-8") if skill_md.exists() else "",
        skill_dir=skill_dir,
        repo_license=args.repo_license,
    )
    # §3.2.2 normalisation is a mapping task for the general model, not for the reader
    pipeline = LiSkillPipeline(llm=_load_llm(args, "for_normalization"))
    doc = pipeline.extract([artifact])[0]
    print(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    outcome = run_demo(
        size=args.size,
        workflows=0 if args.intra_only else args.workflows,
        seed=args.seed,
        out_dir=args.out,
        collect=False,
        understanding_sample=0,
        quiet=True,
        # §4.4.2: with --use-llm the chains come from the drafting model instead
        # of the seeded offline generator
        workflow_client=_load_llm(args, "for_drafting"),
    )
    print(json.dumps(outcome.summary, ensure_ascii=False, indent=2))
    print(f"report: {outcome.report_path}")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from .understand.train_lora import LoRAConfig, train

    config = LoRAConfig(
        train_file=args.train,
        dev_file=args.dev,
        base_model=args.base_model,
        output_dir=args.out or "out/lora",
        epochs=args.epochs,
    )
    print(train(config))
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liskill", description="LiSkill — term-level license conflict detection")
    parser.add_argument("--version", action="version", version=f"liskill {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run the end-to-end offline demo")
    demo.add_argument("--size", type=int, default=600, help="number of synthetic skills")
    demo.add_argument("--workflows", type=int, default=200)
    demo.add_argument("--seed", type=int, default=20260501)
    demo.add_argument("--out", default="out")
    demo.add_argument("--no-collect", action="store_true", help="skip the collection stage")
    demo.add_argument("--understanding-sample", type=int, default=1200)
    demo.add_argument("--quiet", action="store_true", help="do not print the report")
    demo.set_defaults(func=cmd_demo)

    collect = sub.add_parser("collect", help="collect skills from the supported markets")
    collect.add_argument("--platforms", nargs="*", choices=platform_names())
    collect.add_argument("--sink", choices=["jsonl", "memory", "mongo"], default="jsonl")
    collect.add_argument("--out", default="")
    collect.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    collect.add_argument("--db", default="liskill")
    collect.add_argument("--collection", default="skills")
    collect.add_argument("--offline", action="store_true", help="replay the bundled sample payloads")
    collect.add_argument("--max-pages", type=int, default=0)
    collect.set_defaults(func=cmd_collect)

    spdx = sub.add_parser("spdx", help="crawl the SPDX license list and legal texts")
    spdx.add_argument("--out", default="data/spdx_licenses")
    spdx.add_argument("--limit", type=int, default=0, help="cap new detail requests (smoke test)")
    spdx.add_argument("--with-template", action="store_true", help="also store standardLicenseTemplate")
    spdx.add_argument("--refresh", action="store_true", help="ignore the resume checkpoint")
    spdx.add_argument("--rate", type=float, default=2.0, help="detail requests per second")
    spdx.set_defaults(func=cmd_spdx)

    reference = sub.add_parser("reference", help="build the license reference set")
    reference.add_argument("--out", default="out/licenses.json")
    reference.add_argument("--include-custom", action="store_true")
    reference.add_argument(
        "--spdx-dir", default="", help="build from a crawled SPDX corpus instead of the bundled texts"
    )
    reference.set_defaults(func=cmd_reference)

    termdb = sub.add_parser("termdb", help="build the term database (§3.4.1)")
    termdb.add_argument("--out", default="out/termdb.json")
    termdb.add_argument("--show", nargs="*")
    termdb.add_argument(
        "--use-llm",
        action="store_true",
        help="read the licences with the fine-tuned model of §3.3.3 "
        "(default: the offline heuristic reader)",
    )
    termdb.set_defaults(func=cmd_termdb)

    dataset = sub.add_parser("dataset", help="build the license understanding dataset (§3.3.2)")
    dataset.add_argument("--sample", type=int, default=1200)
    dataset.add_argument("--out", default="out/understanding")
    dataset.add_argument(
        "--use-llm",
        action="store_true",
        help="pre-annotate with DeepSeek-V4-Flash-0731 instead of the offline reader",
    )
    dataset.add_argument(
        "--use-embedding",
        action="store_true",
        help="de-duplicate with Qwen3-Embedding-0.6B instead of the n-gram stand-in "
        "(needs pip install 'liskill[embed]')",
    )
    dataset.set_defaults(func=cmd_dataset)

    extract = sub.add_parser("extract", help="extract the three-level licenses of one skill")
    extract.add_argument("path")
    extract.add_argument("--repo-license", default="")
    extract.add_argument(
        "--use-llm",
        action="store_true",
        help="normalise free-text declarations with the local base Qwen3.5-9B (§3.2.2)",
    )
    extract.set_defaults(func=cmd_extract)

    detect = sub.add_parser("detect", help="run conflict detection on the demo corpus")
    detect.add_argument("--size", type=int, default=600)
    detect.add_argument("--workflows", type=int, default=200)
    detect.add_argument("--seed", type=int, default=20260501)
    detect.add_argument("--out", default="out")
    detect.add_argument("--intra-only", action="store_true")
    detect.add_argument(
        "--use-llm",
        action="store_true",
        help="generate the workflows with DeepSeek-V4-Flash-0731 (§4.4.2)",
    )
    detect.set_defaults(func=cmd_detect)

    train = sub.add_parser("train", help="LoRA fine-tuning of the license understanding model")
    train.add_argument("--train", default="out/understanding/train.jsonl")
    train.add_argument("--dev", default="out/understanding/dev.jsonl")
    train.add_argument("--base-model", default="Qwen/Qwen3.5-9B")
    train.add_argument("--out", default="out/qwen3.5-9b-liskill-lora")
    train.add_argument("--epochs", type=int, default=5)
    train.set_defaults(func=cmd_train)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
