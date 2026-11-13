"""Per-platform list parsers.

Ported from the early collectors delivered by the crawler engineer (kept outside
this artifact for provenance) and decoupled from the internal
``Request``/``Scheduler`` objects: a parser is now a pure function
``parse(platform, payload, page) -> (records, has_more)``.  That makes every
parser testable against a stored payload, with no network access.

Records are normalised to the subset of Table 4 that can be filled at list time;
``skill_md_content`` and the repository license are filled by
:mod:`liskill.data_collection_preprocessing.skills.enrich`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from .platforms import NORMALIZED_FIELDS, Platform

SKILL_MD_MARKER = "skill.md"


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def github_full_name(url: str) -> str:
    """``https://github.com/owner/repo/tree/main/skill`` -> ``owner/repo``."""
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    if "github.com" not in host:
        return ""
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        return ""
    return f"{segments[0]}/{segments[1]}"


def repo_relative_path(url: str) -> str:
    """Path of the skill inside its repository (``""`` when the repo root)."""
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    segments = [s for s in parsed.path.split("/") if s]
    if "tree" in segments:
        index = segments.index("tree")
        rest = segments[index + 2 :]  # skip the branch name
        return "/".join(rest)
    if "blob" in segments:
        index = segments.index("blob")
        rest = segments[index + 2 : -1]
        return "/".join(rest)
    return ""


def _empty_record(platform: str) -> Dict[str, Any]:
    return {name: "" for name in NORMALIZED_FIELDS} | {"platform": platform}


def _finalise(record: Dict[str, Any], platform: str) -> Dict[str, Any]:
    base = _empty_record(platform)
    base.update({k: v for k, v in record.items() if v is not None})
    base["name"] = str(base.get("name") or "").strip()
    base["description"] = str(base.get("description") or "").strip()
    repo_url = str(base.get("repo_url") or "").strip()
    if repo_url and not base.get("repo_full_name"):
        base["repo_full_name"] = github_full_name(repo_url)
    if repo_url and not base.get("relative_path"):
        base["relative_path"] = repo_relative_path(repo_url)
    if repo_url and not base.get("default_branch") and "/tree/" in repo_url:
        segments = [s for s in urlparse(repo_url).path.split("/") if s]
        if "tree" in segments:
            base["default_branch"] = segments[segments.index("tree") + 1]
    return base


def finalise_record(platform: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """Public wrapper around the normaliser, used by the runner and detail merge."""
    return _finalise(record, platform)


def _load_json(payload: str) -> Dict[str, Any]:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        # some platforms embed a JSON blob inside the HTML document
        match = re.search(r"(\{.*\})", payload, re.S)
        if match:
            try:
                return {"_embedded": json.loads(match.group(1))}
            except json.JSONDecodeError:
                pass
    return {}


def _unescape_blob(raw: str) -> str:
    for old, new in (('\\"', '"'), ("\\'", "'"), ("\\\\", "\\")):
        raw = raw.replace(old, new)
    return raw.strip()


def _normalise_escapes(payload: str) -> str:
    """Collapse double-escaped JSON (``\\\\"``) so one regex serves both shapes."""
    return payload.replace('\\\\"', '\\"')


def _embedded_json(payload: str, key: str) -> List[Any]:
    """Pull a JSON array embedded in an HTML document under ``key``.

    Pages such as lobehub and skillszoo ship the payload as an escaped JSON
    string inside a hydration script, so the array is located by scanning for
    the key and then bracket-matching the value — a regex cannot tell the
    closing ``]`` of the array from the escaped ``\\"]`` sequences around it.
    """
    text = _normalise_escapes(payload)
    pattern = re.compile(
        r'\\{0,2}"?' + re.escape(key) + r'\\{0,2}"?\s*:\s*', re.S
    )
    for match in pattern.finditer(text):
        start = text.find("[", match.end())
        if start < 0:
            continue
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(_unescape_blob(text[start : index + 1]))
                    except json.JSONDecodeError:
                        break
                    return data if isinstance(data, list) else []
    return []


# --------------------------------------------------------------------------- #
# JSON APIs
# --------------------------------------------------------------------------- #
def parse_clawhub(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    items = data.get("items") or data.get("skills") or []
    records = []
    for item in items:
        tags = item.get("tags") or {}
        version = tags.get("latest") if isinstance(tags, dict) else None
        repo = item.get("repository") or item.get("repo") or ""
        records.append(
            _finalise(
                {
                    "name": item.get("slug") or item.get("name") or "",
                    "description": item.get("summary") or item.get("description") or "",
                    "author": item.get("ownerHandle") or item.get("author") or "",
                    "repo_url": repo,
                    "skill_md_content": item.get("content") or "",
                },
                platform.name,
            )
        )
    has_more = bool(data.get("nextCursor"))
    return [r for r in records if r["name"]], has_more


def parse_agentskills_in(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    items = data.get("skills") or []
    records = [
        _finalise(
            {
                "name": item.get("name") or "",
                "description": item.get("description") or "",
                "author": item.get("author") or "",
                "repo_url": item.get("githubUrl") or "",
                "skill_md_content": item.get("skillMdContent") or item.get("content") or "",
            },
            platform.name,
        )
        for item in items
    ]
    total = int(data.get("total") or 0)
    offset = int(data.get("offset") or 0) + int(data.get("limit") or platform.page_size)
    return records, offset < total


def parse_skills_lc(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload).get("data") or {}
    pagination = data.get("pagination") or {}
    items = data.get("skills") or []
    records = [
        _finalise(
            {
                "name": item.get("name") or "",
                "description": item.get("description") or "",
                "author": item.get("author") or "",
                "repo_url": item.get("githubUrl") or "",
                "skill_md_content": item.get("content") or "",
            },
            platform.name,
        )
        for item in items
    ]
    current = int(pagination.get("page") or page)
    total_pages = int(pagination.get("totalPages") or current)
    return records, current < total_pages


def parse_skills_sh(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    items = data.get("skills") or []
    records = []
    for item in items:
        source = item.get("source") or ""
        repo_url = f"https://github.com/{source}" if source and "github.com" not in source else source
        records.append(
            _finalise(
                {
                    "name": item.get("name") or item.get("slug") or "",
                    "description": item.get("description") or "",
                    "author": source.split("/")[0] if "/" in source else "",
                    "repo_url": repo_url,
                },
                platform.name,
            )
        )
    return records, bool(data.get("hasMore"))


def parse_skillmaps(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    items = data.get("items") or data.get("skills") or []
    records = [
        _finalise(
            {
                "name": item.get("name") or item.get("slug") or "",
                "description": item.get("description") or "",
                "author": item.get("author") or "",
                "repo_url": item.get("github_url") or item.get("repo_url") or "",
            },
            platform.name,
        )
        for item in items
    ]
    total_pages = int(data.get("totalPages") or data.get("total_pages") or page)
    return records, page < total_pages


def parse_smithery(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    pagination = data.get("pagination") or {}
    items = data.get("skills") or []
    records = [
        _finalise(
            {
                "name": item.get("slug") or item.get("name") or "",
                "description": item.get("description") or "",
                "author": item.get("owner") or "",
                "repo_url": item.get("gitUrl") or item.get("homepage") or "",
            },
            platform.name,
        )
        for item in items
    ]
    current = int(pagination.get("currentPage") or page)
    total_pages = int(pagination.get("totalPages") or current)
    return records, current < total_pages


def parse_skills_palebluedot(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    pagination = data.get("pagination") or {}
    items = data.get("skills") or []
    records = []
    for item in items:
        owner = item.get("githubOwner") or ""
        repo = item.get("githubRepo") or ""
        path = item.get("skillPath") or ""
        repo_url = f"https://github.com/{owner}/{repo}" + (f"/tree/main/{path}" if path else "")
        records.append(
            _finalise(
                {
                    "name": item.get("name") or path.rstrip("/").split("/")[-1] or "",
                    "description": item.get("description") or "",
                    "author": owner,
                    "repo_url": repo_url,
                },
                platform.name,
            )
        )
    current = int(pagination.get("page") or page)
    total_pages = int(pagination.get("totalPages") or current)
    return records, current < total_pages


def parse_skillsdirectory(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    pagination = data.get("pagination") or {}
    items = data.get("skills") or []
    records = []
    for item in items:
        source_url = item.get("sourceUrl") or ""
        skill_file = item.get("skillFilePath") or ""
        repo_url = source_url
        if skill_file and "/blob/" in skill_file:
            repo_url = skill_file.split("/blob/")[0]
        records.append(
            _finalise(
                {
                    "name": item.get("name") or "",
                    "description": item.get("description") or "",
                    "author": item.get("author") or "",
                    "repo_url": repo_url,
                },
                platform.name,
            )
        )
    current = int(pagination.get("page") or page)
    total_pages = int(pagination.get("totalPages") or current)
    return records, current < total_pages


def parse_skillsmk(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    meta = data.get("meta") or {}
    items = data.get("data") or []
    records = []
    for item in items:
        repo_full_name = item.get("repo_full_name") or ""
        path = item.get("skill_path") or ""
        repo_url = f"https://github.com/{repo_full_name}" + (f"/tree/main/{path}" if path else "")
        records.append(
            _finalise(
                {
                    "name": item.get("name") or (path.rstrip("/").split("/")[-1] if path else ""),
                    "description": item.get("description") or "",
                    "author": repo_full_name.split("/")[0] if "/" in repo_full_name else "",
                    "repo_url": repo_url,
                },
                platform.name,
            )
        )
    current = int(meta.get("current_page") or page)
    total_pages = int(meta.get("last_page") or current)
    return records, current < total_pages


def parse_agnxi(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    items = data.get("skills") or []
    records = []
    for item in items:
        source_url = item.get("url") or ""
        repo_url = source_url
        if "/blob/" in source_url:
            repo_url = source_url.split("/blob/")[0]
        records.append(
            _finalise(
                {
                    "name": item.get("name") or "",
                    "description": item.get("description") or "",
                    "author": item.get("author") or "",
                    "repo_url": repo_url,
                },
                platform.name,
            )
        )
    current = int(data.get("page") or page)
    total_pages = int(data.get("totalPages") or current)
    return records, current < total_pages


def parse_agent_skills_md(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    data = _load_json(payload)
    items = data.get("results") or data.get("skills") or []
    records = [
        _finalise(
            {
                "name": item.get("name") or item.get("slug") or "",
                "description": item.get("description") or "",
                "author": item.get("author") or "",
                "repo_url": item.get("repoUrl") or item.get("repository") or "",
            },
            platform.name,
        )
        for item in items
    ]
    return records, False  # single full dump


# --------------------------------------------------------------------------- #
# HTML pages with an embedded JSON blob
# --------------------------------------------------------------------------- #
def parse_lobehub(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    items = _embedded_json(payload, "data")
    if not items:
        return [], False
    records = [
        _finalise(
            {
                "name": item.get("name") or item.get("identifier") or "",
                "description": item.get("description") or "",
                "author": item.get("author") or "",
                "repo_url": item.get("homepage") or "",
            },
            platform.name,
        )
        for item in items
    ]
    return records, bool(records)


def parse_skillszoo(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    items = _embedded_json(payload, "categorySkills")
    if not items:
        return [], False
    records = []
    for item in items:
        github_url = item.get("githubUrl") or ""
        records.append(
            _finalise(
                {
                    "name": item.get("name") or item.get("slug") or "",
                    "description": item.get("description") or "",
                    "author": item.get("author") or "",
                    "repo_url": github_url,
                },
                platform.name,
            )
        )
    return records, bool(records)


def parse_toprankskills(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    cards = re.findall(r'<div class="skill-card".*?</div>\s*</div>', payload, re.S)
    if not cards:
        cards = re.findall(r'<div class="skill-card".*?(?=<div class="skill-card"|$)', payload, re.S)
    records = []
    for card in cards:
        name = re.search(r'class="text-lg[^"]*"[^>]*>([^<]+)<', card)
        desc = re.search(r'class="line-clamp-2[^"]*"[^>]*>([^<]+)<', card)
        links = re.findall(r'<a[^>]+href="([^"]+)"', card)
        github_url = next((link for link in links if "github.com" in link), "")
        slug = re.search(r'class="[^"]*font-mono[^"]*"[^>]*>([^<]+)<', card)
        records.append(
            _finalise(
                {
                    "name": (name.group(1).strip() if name else (slug.group(1).strip() if slug else "")),
                    "description": desc.group(1).strip() if desc else "",
                    "author": github_full_name(github_url).split("/")[0],
                    "repo_url": github_url,
                },
                platform.name,
            )
        )
    return [r for r in records if r["name"]], bool(records)


# --------------------------------------------------------------------------- #
# platforms added for the released release (skillsmp / skills.rest / awesome)
# --------------------------------------------------------------------------- #
def parse_skillsmp(platform: Platform, payload: str, page: int) -> Tuple[List[dict], bool]:
    """skillsmp's documented search API (``/api/v1/skills/search``).

    The response is ``{success, data: {skills, pagination, filters}, meta}``.  The
    list endpoint carries no SKILL.md body; the GitHub side of
    :mod:`liskill.data_collection_preprocessing.skills.enrich` fills it from ``githubUrl``.
    """
    data = _load_json(payload)
    body = data.get("data") or {}
    items = body.get("skills") or []
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        records.append(
            _finalise(
                {
                    "name": item.get("name") or "",
                    "description": item.get("description") or "",
                    "author": item.get("author") or "",
                    "repo_url": item.get("githubUrl") or "",
                },
                platform.name,
            )
        )
    pagination = body.get("pagination") or {}
    return [r for r in records if r["name"]], bool(pagination.get("hasNext"))


def _flight_payload(payload: str) -> str:
    """Concatenate the React Server Component flight chunks of a page.

    Next.js streams the rendered tree as
    ``self.__next_f.push([1,"<escaped json string>"])``; each chunk is a JSON
    string literal, so decoding them one by one is lossless (unlike a blanket
    ``unicode_escape`` pass, which mangles non-ASCII descriptions).
    """
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', payload, re.S)
    parts: List[str] = []
    for chunk in chunks:
        try:
            parts.append(json.loads(chunk))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def _flight_array(text: str, key: str) -> List[Any]:
    """Locate ``"<key>":[...]`` inside a flight payload and decode it.

    Flight serialises missing values as the string sentinel ``"$undefined"``,
    which is not valid JSON; it is mapped to ``null`` before parsing.
    """
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*\[')
    for match in pattern.finditer(text):
        start = match.end() - 1
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    blob = text[start : index + 1].replace('"$undefined"', "null")
                    try:
                        data = json.loads(blob)
                    except json.JSONDecodeError:
                        break
                    return data if isinstance(data, list) else []
    return []


def parse_awesome_agent_skills(
    platform: Platform, payload: str, page: int
) -> Tuple[List[dict], bool]:
    """awesome-agent-skills ships its whole catalogue in a single page.

    The record shape is ``{id, name, description, url, category, platforms,
    source, section, githubOwner, githubRepo, stars, lastUpdated, ...}``.
    """
    items = _flight_array(_flight_payload(payload), "skills")
    if not items:
        # The catalogue is either absent or the flight framing changed; failing
        # loudly beats reporting an empty market.
        raise ValueError(
            "awesome-agent-skills: no 'skills' array in the React flight payload "
            "(the page layout may have changed — re-check the endpoint)"
        )
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        repo_url = item.get("url") or ""
        if not repo_url:
            owner, repo = item.get("githubOwner") or "", item.get("githubRepo") or ""
            repo_url = f"https://github.com/{owner}/{repo}" if owner and repo else ""
        records.append(
            _finalise(
                {
                    "name": item.get("name") or "",
                    "description": item.get("description") or "",
                    "author": item.get("githubOwner") or "",
                    "repo_url": repo_url,
                },
                platform.name,
            )
        )
    # one page is the whole market: nothing is left to page through
    return [r for r in records if r["name"]], False


def parse_skills_rest_sitemap(
    platform: Platform, payload: str, page: int
) -> Tuple[List[dict], bool]:
    """Enumerate ``/skill/<slug>`` entries of one skills.rest sitemap.

    ``robots.txt`` disallows ``/api/`` and every query string, so the published
    sitemap index is the only crawl path the site sanctions.  Each sitemap holds
    up to 10,000 pointers; the pointers are not records yet, which is why
    ``Platform.detail`` asks the runner to resolve them.
    """
    locations = re.findall(r"<loc>([^<]+)</loc>", payload)
    seeds = []
    for url in locations:
        if "/skill/" not in url:
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        seeds.append(
            finalise_record(platform.name, {"name": slug, "description": "", "detail_url": url})
        )
    return seeds, bool(locations)


RE_JSONLD = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
RE_GITHUB_LINK = re.compile(r'href="(https://github\.com/[^"]+)"')


def parse_skills_rest_detail(
    platform: Platform, payload: str, record: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve one skills.rest skill page into the Table 4 fields.

    The page carries a schema.org ``SoftwareApplication`` block with the real
    name and description, and links out to the skill's GitHub directory.  The
    rendered article is a generated summary rather than the SKILL.md body, so
    ``skill_md_content`` is left to the GitHub enrichment step.
    """
    name = ""
    description = ""
    author = ""
    for block in RE_JSONLD.findall(payload):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        graph = data.get("@graph") if isinstance(data, dict) else None
        nodes = graph if isinstance(graph, list) else [data]
        for node in nodes:
            if not isinstance(node, dict) or node.get("@type") != "SoftwareApplication":
                continue
            name = str(node.get("name") or "")
            description = str(node.get("description") or "")
            creator = node.get("author") or node.get("creator") or {}
            if isinstance(creator, dict):
                author = str(creator.get("name") or "")
            break
        if name:
            break

    repo_url = ""
    for link in RE_GITHUB_LINK.findall(payload):
        if "/skills/" in link or "/tree/" in link or "/blob/" in link:
            repo_url = link
            break
    if not repo_url:
        matches = RE_GITHUB_LINK.findall(payload)
        repo_url = matches[0] if matches else ""

    return {
        "name": name or record.get("name") or "",
        "description": description,
        "author": author,
        "repo_url": repo_url,
    }


PARSERS = {
    "clawhub": parse_clawhub,
    "agentskills_in": parse_agentskills_in,
    "skills_lc": parse_skills_lc,
    "skills_sh": parse_skills_sh,
    "skillmaps": parse_skillmaps,
    "smithery": parse_smithery,
    "skills_palebluedot": parse_skills_palebluedot,
    "skillsdirectory": parse_skillsdirectory,
    "skillsmk": parse_skillsmk,
    "agnxi": parse_agnxi,
    "agent_skills_md": parse_agent_skills_md,
    "lobehub": parse_lobehub,
    "skillszoo": parse_skillszoo,
    "toprankskills": parse_toprankskills,
    "skillsmp": parse_skillsmp,
    "skills_rest_sitemap": parse_skills_rest_sitemap,
    "awesome_agent_skills": parse_awesome_agent_skills,
}

#: detail resolvers: ``parse(platform, payload, seed_record) -> field dict``
DETAIL_PARSERS = {
    "skills_rest_detail": parse_skills_rest_detail,
}


def get_parser(platform: Platform):
    try:
        return PARSERS[platform.parser]
    except KeyError as exc:  # pragma: no cover - guarded by platforms.py
        raise KeyError(f"no parser registered for {platform.name!r}") from exc


def get_detail_parser(name: str):
    try:
        return DETAIL_PARSERS[name]
    except KeyError as exc:  # pragma: no cover - guarded by platforms.py
        raise KeyError(f"no detail parser registered for {name!r}") from exc
