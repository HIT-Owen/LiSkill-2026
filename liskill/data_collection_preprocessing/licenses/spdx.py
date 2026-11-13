"""SPDX license corpus crawler (§3.1.2 — SPDX source).

The reference set needs the *full legal texts* of the standard licenses, not just
their identifiers: §3.2.2 resolves ``Refer-Local`` declarations by hashing the
text, and §3.3 / §3.4.1 need the clauses before the term-attitude model can
annotate them.  Two official endpoints provide them:

* ``https://spdx.org/licenses/licenses.json`` — the license list itself;
* ``https://spdx.org/licenses/<licenseId>.json`` — the detail document, carrying
  ``licenseText``, ``standardLicenseTemplate``, ``isOsiApproved``, ``isFsfLibre``,
  ``isDeprecatedLicenseId`` and ``seeAlso``.

The crawl is resumable: already-fetched identifiers are read back from
``texts.jsonl``, so an interrupted run continues instead of restarting (740
detail requests at two per second take about six minutes).

Output layout, both files small enough to ship with the artifact::

    <out>/licenses.json   index: metadata only, one entry per license
    <out>/texts.jsonl     full licence text, one JSON object per line

``licenseTextHtml`` and ``standardLicenseTemplate`` are skipped by default —
together they are roughly four times the size of the plain text, and nothing in
the pipeline consumes the HTML rendering.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

SPDX_INDEX_URL = "https://spdx.org/licenses/licenses.json"
SPDX_DETAIL_URL = "https://spdx.org/licenses/{license_id}.json"
USER_AGENT = "LiSkill/0.1 (license conflict research; +https://spdx.org/licenses/)"

INDEX_FILE = "licenses.json"
TEXT_FILE = "texts.jsonl"


# --------------------------------------------------------------------------- #
# record
# --------------------------------------------------------------------------- #
@dataclass
class SpdxLicense:
    """One license of the SPDX License List."""

    license_id: str
    name: str
    license_text: str = ""
    standard_license_template: str = ""
    is_osi_approved: bool = False
    is_fsf_libre: bool = False
    is_deprecated: bool = False
    see_also: List[str] = field(default_factory=list)
    details_url: str = ""

    @property
    def text_sha256(self) -> str:
        """Hash of the legal text, matching ``licenses.reference.sha256_text``."""
        import hashlib

        return hashlib.sha256((self.license_text or "").strip().encode("utf-8")).hexdigest()

    def to_index(self) -> Dict[str, object]:
        return {
            "license_id": self.license_id,
            "name": self.name,
            "is_osi_approved": self.is_osi_approved,
            "is_fsf_libre": self.is_fsf_libre,
            "is_deprecated": self.is_deprecated,
            "see_also": list(self.see_also),
            "details_url": self.details_url,
            "text_sha256": self.text_sha256,
            "text_chars": len(self.license_text or ""),
        }

    def to_text_row(self, with_template: bool = False) -> Dict[str, object]:
        row: Dict[str, object] = {
            "license_id": self.license_id,
            "name": self.name,
            "license_text": self.license_text,
        }
        if with_template:
            row["standard_license_template"] = self.standard_license_template
        return row


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def parse_index(payload: str) -> Dict[str, object]:
    """``licenses.json`` -> ``{licenseListVersion, releaseDate, licenses}``."""
    data = json.loads(payload)
    licenses = data.get("licenses")
    if not isinstance(licenses, list):
        raise ValueError("unexpected SPDX index shape: no 'licenses' array")
    return {
        "licenseListVersion": data.get("licenseListVersion", ""),
        "releaseDate": data.get("releaseDate", ""),
        "licenses": licenses,
    }


def parse_license(payload: str, fallback_id: str = "") -> SpdxLicense:
    """One detail document -> :class:`SpdxLicense`."""
    data = json.loads(payload)
    license_id = data.get("licenseId") or fallback_id
    if not license_id:
        raise ValueError("detail document carries no licenseId")
    return SpdxLicense(
        license_id=license_id,
        name=data.get("name") or license_id,
        license_text=data.get("licenseText") or "",
        standard_license_template=data.get("standardLicenseTemplate") or "",
        is_osi_approved=bool(data.get("isOsiApproved", False)),
        is_fsf_libre=bool(data.get("isFsfLibre", False)),
        is_deprecated=bool(data.get("isDeprecatedLicenseId", False)),
        see_also=[str(url) for url in data.get("seeAlso") or []],
        details_url=SPDX_DETAIL_URL.format(license_id=license_id),
    )


# --------------------------------------------------------------------------- #
# transport
# --------------------------------------------------------------------------- #
def http_get(url: str, timeout: int = 30, retries: int = 3) -> str:
    """Plain ``urllib`` GET with bounded exponential back-off."""
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 ** attempt)
    raise RuntimeError(f"GET failed: {url} ({last_error})")


# --------------------------------------------------------------------------- #
# crawl
# --------------------------------------------------------------------------- #
@dataclass
class CrawlStats:
    list_version: str = ""
    total: int = 0
    fetched: int = 0
    skipped_existing: int = 0
    empty_text: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "licenseListVersion": self.list_version,
            "total": self.total,
            "fetched": self.fetched,
            "skipped_existing": self.skipped_existing,
            "empty_text": self.empty_text,
            "failed": len(self.errors),
            "errors": self.errors,
        }


def _load_done(text_path: Path) -> Dict[str, Dict[str, object]]:
    done: Dict[str, Dict[str, object]] = {}
    if not text_path.exists():
        return done
    with text_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn last line from an interrupted run
            if row.get("license_id"):
                done[str(row["license_id"])] = row
    return done


def crawl(
    out_dir: str | Path = "data/spdx_licenses",
    *,
    limit: int = 0,
    with_template: bool = False,
    refresh: bool = False,
    requests_per_second: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> CrawlStats:
    """Fetch the SPDX license list and every license's legal text.

    ``limit`` caps the number of *new* detail requests (useful for a smoke test);
    ``refresh`` ignores the checkpoint and re-fetches everything.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    text_path = out / TEXT_FILE
    index_path = out / INDEX_FILE

    stats = CrawlStats()
    index = parse_index(http_get(SPDX_INDEX_URL))
    stats.list_version = str(index["licenseListVersion"])
    entries: Sequence[Dict[str, object]] = index["licenses"]  # type: ignore[assignment]
    stats.total = len(entries)
    log(f"[spdx] list {stats.list_version}: {stats.total} licenses")

    done = {} if refresh else _load_done(text_path)
    stats.skipped_existing = len(done) if not refresh else 0
    if done:
        log(f"[spdx] resuming, {len(done)} already on disk")

    interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
    results: Dict[str, SpdxLicense] = {}

    for entry in entries:
        license_id = str(entry.get("licenseId") or "")
        if not license_id:
            continue
        row = done.get(license_id)
        if row is not None:
            results[license_id] = SpdxLicense(
                license_id=license_id,
                name=str(row.get("name") or entry.get("name") or ""),
                license_text=str(row.get("license_text") or ""),
                standard_license_template=str(row.get("standard_license_template") or ""),
                is_osi_approved=bool(entry.get("isOsiApproved", False)),
                is_deprecated=bool(entry.get("isDeprecatedLicenseId", False)),
                see_also=[str(u) for u in entry.get("seeAlso") or []],
                details_url=str(entry.get("detailsUrl") or ""),
            )
            continue
        if limit and stats.fetched >= limit:
            continue

        url = str(entry.get("detailsUrl") or SPDX_DETAIL_URL.format(license_id=license_id))
        try:
            license_obj = parse_license(http_get(url), fallback_id=license_id)
        except Exception as exc:  # keep going: one bad license must not stop the crawl
            stats.errors.append({"license_id": license_id, "error": str(exc)})
            log(f"[spdx] FAILED {license_id}: {exc}")
            continue

        license_obj.name = license_obj.name or str(entry.get("name") or "")
        license_obj.see_also = license_obj.see_also or [str(u) for u in entry.get("seeAlso") or []]
        license_obj.is_osi_approved = license_obj.is_osi_approved or bool(entry.get("isOsiApproved", False))
        license_obj.is_deprecated = license_obj.is_deprecated or bool(entry.get("isDeprecatedLicenseId", False))
        if not license_obj.license_text.strip():
            stats.empty_text += 1

        results[license_id] = license_obj
        stats.fetched += 1
        if stats.fetched % 50 == 0:
            log(f"[spdx] {stats.fetched} fetched / {stats.total} listed")
        if interval:
            sleep(interval)

    # Atomic rewrite so an interrupted run never leaves a half-written corpus.
    ordered = [
        results[str(entry["licenseId"])]
        for entry in entries
        if str(entry.get("licenseId") or "") in results
    ]
    tmp_text = text_path.with_suffix(".jsonl.tmp")
    with tmp_text.open("w", encoding="utf-8") as handle:
        for license_obj in ordered:
            handle.write(
                json.dumps(license_obj.to_text_row(with_template), ensure_ascii=False) + "\n"
            )
    tmp_text.replace(text_path)

    index_payload = {
        "source": SPDX_INDEX_URL,
        "licenseListVersion": index["licenseListVersion"],
        "releaseDate": index["releaseDate"],
        "count": len(ordered),
        "licenses": [license_obj.to_index() for license_obj in ordered],
    }
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log(f"[spdx] wrote {len(ordered)} texts -> {text_path}")
    log(f"[spdx] wrote index -> {index_path}")
    return stats


# --------------------------------------------------------------------------- #
# load back
# --------------------------------------------------------------------------- #
def load(out_dir: str | Path = "data/spdx_licenses") -> List[SpdxLicense]:
    """Read the crawled corpus back into :class:`SpdxLicense` objects."""
    out = Path(out_dir)
    index_path = out / INDEX_FILE
    text_path = out / TEXT_FILE
    if not text_path.exists():
        raise FileNotFoundError(f"no SPDX corpus at {text_path}; run `liskill cli spdx` first")

    index: Dict[str, Dict[str, object]] = {}
    if index_path.exists():
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        index = {str(item["license_id"]): item for item in payload.get("licenses", [])}

    licenses: List[SpdxLicense] = []
    with text_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            meta = index.get(str(row.get("license_id")), {})
            licenses.append(
                SpdxLicense(
                    license_id=str(row["license_id"]),
                    name=str(row.get("name") or meta.get("name") or ""),
                    license_text=str(row.get("license_text") or ""),
                    standard_license_template=str(row.get("standard_license_template") or ""),
                    is_osi_approved=bool(meta.get("is_osi_approved", False)),
                    is_fsf_libre=bool(meta.get("is_fsf_libre", False)),
                    is_deprecated=bool(meta.get("is_deprecated", False)),
                    see_also=[str(u) for u in meta.get("see_also") or []],
                    details_url=str(meta.get("details_url") or ""),
                )
            )
    return licenses


def build_reference_set(out_dir: str | Path = "data/spdx_licenses", include_deprecated: bool = True):
    """Build a :class:`~liskill.data_collection_preprocessing.licenses.reference.ReferenceSet` from the corpus."""
    from .reference import ReferenceSet

    reference = ReferenceSet()
    for license_obj in load(out_dir):
        if license_obj.is_deprecated and not include_deprecated:
            continue
        reference.add_from_text(
            license_obj.license_id,
            license_obj.name,
            license_obj.license_text,
            spdx_id=license_obj.license_id,
            osi_approved=license_obj.is_osi_approved,
            deprecated=license_obj.is_deprecated,
            sources=[
                {
                    "source": "SPDX",
                    "url": license_obj.details_url
                    or SPDX_DETAIL_URL.format(license_id=license_obj.license_id),
                }
            ],
        )
    return reference
