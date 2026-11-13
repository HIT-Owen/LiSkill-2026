"""Collection driver.

Paging is driven by the platform's own pagination (``totalPages`` / ``hasMore``
/ cursor) instead of a hard-coded page cap: the early collectors shipped fixed
``max_pages`` values that could silently truncate a market, which is why the
released runner treats ``max_pages`` as an opt-in safety valve only.

``offline=True`` replays the bundled sample payloads of
:mod:`liskill.data_collection_preprocessing.skills.fixtures`, so the whole pipeline can be demonstrated and
tested without network access.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from .clean import CleaningStats, clean_records
from .fixtures import FIXTURES
from .http import HttpClient, RateLimit
from .platforms import Platform, get, platform_names
from .sink import BaseSink, CursorStore, MemorySink
from .spiders import finalise_record, get_detail_parser, get_parser


@dataclass
class PlatformStats:
    platform: str
    pages: int = 0
    records: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {"platform": self.platform, "pages": self.pages, "records": self.records}


@dataclass
class CollectionReport:
    platforms: List[PlatformStats] = field(default_factory=list)
    raw_records: int = 0
    unique_records: int = 0
    cleaning: Optional[CleaningStats] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "platforms": [p.to_dict() for p in self.platforms],
            "raw_records": self.raw_records,
            "unique_records": self.unique_records,
            "cleaning": self.cleaning.to_dict() if self.cleaning else {},
        }


class Collector:
    """Fetch, parse, clean and persist skills from the supported markets."""

    def __init__(
        self,
        sink: Optional[BaseSink] = None,
        http: Optional[HttpClient] = None,
        state: Optional[CursorStore] = None,
        offline: bool = False,
        clean: bool = True,
    ) -> None:
        self.sink = sink if sink is not None else MemorySink()
        self._http = http
        self.state = state or CursorStore(None)
        self.offline = offline
        self.clean = clean
        self.cleaned: List[Dict[str, object]] = []

    # ------------------------------------------------------------------ helpers
    def _client(self, platform: Platform) -> HttpClient:
        return self._http or HttpClient(rate_limit=RateLimit(*platform.rate_limit))

    def _payload(self, platform: Platform, page: int) -> Optional[str]:
        if not self.offline:
            return None
        payloads = FIXTURES.get(platform.name, [])
        if page - 1 < len(payloads):
            return payloads[page - 1]
        return None

    def _fetch(self, platform: Platform, page: int, params: Dict[str, object]) -> Optional[str]:
        if self.offline:
            return self._payload(platform, page)
        url = platform.list_url.format(page=page) if platform.url_template else platform.list_url
        return self._client(platform).get(url, params=params or None)

    def _params(
        self, platform: Platform, page: int, cursor: str, keyword: str = ""
    ) -> Dict[str, object]:
        params: Dict[str, object] = {}
        if platform.paging == "offset":
            params = {"limit": platform.page_size, "offset": (page - 1) * platform.page_size}
        elif platform.paging == "cursor":
            params = {"limit": platform.page_size, "cursor": cursor or None}
        elif platform.paging == "page":
            params = {"page": page, "limit": platform.page_size, "perPage": platform.page_size}
        if platform.keyword_param and keyword:
            params[platform.keyword_param] = keyword
        return params

    # -------------------------------------------------------------------- entry
    def collect_platform(self, name: str, max_pages: int = 0) -> PlatformStats:
        """Collect one market.

        Platforms that reject an empty query (``keyword_param``) are swept over
        their keyword vocabulary and the results unioned; every other platform
        is a single listing walked to its own end.
        """
        platform = get(name)
        stats = PlatformStats(platform=name)
        keywords = list(platform.keywords) if platform.keyword_param else [""]
        for keyword in keywords:
            key = f"{name}|{keyword}" if keyword else name
            pages, count = self._paginate(platform, key, keyword, max_pages)
            stats.pages += pages
            stats.records += count
        return stats

    def _paginate(
        self, platform: Platform, state_key: str, keyword: str, max_pages: int
    ) -> tuple:
        parser = get_parser(platform)
        resume = self.state.get(state_key)
        page = int(resume.get("page", 1)) if isinstance(resume, dict) else 1
        cursor = str(resume.get("cursor", "")) if isinstance(resume, dict) else ""
        limit = platform.max_pages or max_pages
        pages = records_total = 0

        while True:
            params = self._params(platform, page, cursor, keyword)
            payload = self._fetch(platform, page, params)
            if payload is None:
                break
            records, has_more = parser(platform, payload, page)
            records = self._resolve_details(platform, records)
            pages += 1
            records_total += len(records)
            if records:
                self.sink.write(records)
            self.state.set(state_key, {"page": page + 1, "cursor": cursor})
            if not has_more or not records:
                break
            if limit and pages >= limit:
                break
            page += 1
            if platform.paging == "single":
                break
        return pages, records_total

    def _resolve_details(
        self, platform: Platform, records: List[Dict[str, object]]
    ) -> List[Dict[str, object]]:
        """Turn pointer records into real records by fetching each detail page."""
        if not platform.detail or not records:
            return records
        if self.offline:  # the bundled fixtures cover the listing parsers only
            return records
        detail_parser = get_detail_parser(platform.detail)
        client = self._client(platform)
        resolved: List[Dict[str, object]] = []
        for seed in records:
            url = str(seed.get("detail_url") or "")
            if not url:
                continue
            try:
                payload = client.get(url)
            except RuntimeError:
                continue
            fields = detail_parser(platform, payload, seed)
            merged = {k: v for k, v in seed.items() if k != "detail_url"}
            merged.update(fields)
            resolved.append(finalise_record(platform.name, merged))
        return resolved

    def run(self, names: Optional[Sequence[str]] = None, max_pages: int = 0) -> CollectionReport:
        report = CollectionReport()
        targets = list(names) if names else platform_names()
        for name in targets:
            try:
                report.platforms.append(self.collect_platform(name, max_pages=max_pages))
            except Exception as exc:  # keep collecting the other markets
                report.platforms.append(PlatformStats(platform=name))
                print(f"[collect] {name}: {exc}")
        raw = []
        if isinstance(self.sink, MemorySink):
            raw = list(self.sink.records)
        report.raw_records = len(raw) or sum(p.records for p in report.platforms)
        if self.clean and raw:
            unique, stats = clean_records(raw)
            report.cleaning = stats
            report.unique_records = len(unique)
            self.cleaned = unique
        else:
            # streaming sinks (jsonl / mongo) deduplicate on the storage side
            report.unique_records = report.raw_records
        self.sink.close()
        return report
