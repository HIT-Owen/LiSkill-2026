"""Platform declarations (the 17 markets of Table 3).

Each :class:`Platform` records what the fetcher needs — endpoint, paging style,
rate limit, optional auth — and the name of its parser in
:mod:`liskill.data_collection_preprocessing.skills.spiders`.  Three of the seventeen need a shape the plain
list-and-page loop cannot express, so :class:`Platform` carries three extra
switches:

``keyword_param`` / ``keywords``
    skillsmp's search API rejects an empty query, so the catalogue is recovered
    by sweeping a vocabulary and unioning the pages.
``detail``
    skills.rest publishes a sitemap whose entries are pointers; each has to be
    fetched before a record exists.
``url_template``
    the sitemap index is addressed by number rather than by query parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

#: fields every collected record must carry (Table 4, collection stage)
NORMALIZED_FIELDS = (
    "platform",
    "name",
    "description",
    "author",
    "skill_md_content",
    "repo_url",
    "repo_full_name",
    "relative_path",
    "default_branch",
)


@dataclass(frozen=True)
class Platform:
    name: str
    parser: str
    list_url: str
    kind: str = "json"          # json | html | xml
    paging: str = "page"        # page | offset | cursor | single
    rate_limit: tuple = (1, 2.0)
    page_size: int = 100
    auth_env: Optional[str] = None
    max_pages: int = 0          # 0 = follow the platform's own pagination
    notes: str = ""
    extra: Dict[str, object] = field(default_factory=dict)
    #: ``list_url`` carries ``{page}``; the runner substitutes before fetching
    url_template: bool = False
    #: enumeration needs a keyword sweep (the API rejects an empty query)
    keyword_param: Optional[str] = None
    keywords: tuple = ()
    #: listing yields pointers only; the runner fetches each and merges the result
    detail: Optional[str] = None


#: Keyword sweep for skillsmp: its search API answers 400 without ``q`` or
#: ``creator``, so the full catalogue is recovered by querying a vocabulary that
#: covers the skill domain and unioning the results (§3.1.1).
SKILLSMP_KEYWORDS = (
    "pdf", "excel", "word", "ppt", "markdown", "csv", "json", "yaml", "xml", "sql",
    "database", "api", "rest", "graphql", "web", "frontend", "backend", "react",
    "vue", "angular", "node", "python", "typescript", "javascript", "rust", "go",
    "java", "kotlin", "swift", "docker", "kubernetes", "aws", "gcp", "azure",
    "terraform", "ci", "testing", "security", "audit", "review", "refactor",
    "debug", "docs", "design", "ui", "ux", "figma", "image", "video", "audio",
    "ocr", "translate", "search", "scrape", "crawler", "browser", "automation",
    "workflow", "agent", "llm", "prompt", "rag", "embedding", "vector", "data",
    "analytics", "chart", "report", "email", "calendar", "notion", "slack",
    "github", "gitlab", "jira", "linear", "stripe", "payment", "monitor",
    "logging", "metrics", "deploy", "server", "nginx", "redis", "postgres",
    "mysql", "mongo", "kafka", "etl", "pipeline", "notebook", "jupyter",
    "pandas", "numpy", "pytorch", "tensorflow", "training", "inference", "eval",
    "blockchain", "web3", "mobile", "ios", "android", "desktop", "electron",
    "cli", "shell", "bash", "powershell", "linux", "macos", "file", "slides",
    "resume", "legal", "license", "compliance", "research", "paper", "finance",
    "stock", "crypto", "health", "medical", "education", "game", "music",
)


PLATFORMS: Dict[str, Platform] = {
    "clawhub": Platform(
        name="clawhub",
        parser="clawhub",
        list_url="https://clawhub.ai/api/v1/skills",
        paging="cursor",
        rate_limit=(1, 2.0),
        max_pages=0,
        notes="public listing API; the site also exposes the same data over its Convex backend",
    ),
    "agentskills.in": Platform(
        name="agentskills.in",
        parser="agentskills_in",
        list_url="https://www.agentskills.in/api/skills",
        paging="offset",
        rate_limit=(1, 2.0),
        page_size=100,
    ),
    "skills.lc": Platform(
        name="skills.lc",
        parser="skills_lc",
        list_url="https://skills.lc/api/v1/skills/search",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
        auth_env="SKILLS_LC_TOKEN",
    ),
    "skills.sh": Platform(
        name="skills.sh",
        parser="skills_sh",
        list_url="https://skills.sh/api/skills/all-time",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
        extra={"feeds": ["all-time", "trending", "hot"]},
    ),
    "skillmaps": Platform(
        name="skillmaps",
        parser="skillmaps",
        list_url="https://skillmaps.net/v1/skills",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
    ),
    "smithery": Platform(
        name="smithery",
        parser="smithery",
        list_url="https://api.smithery.ai/skills",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
    ),
    "lobehub": Platform(
        name="lobehub",
        parser="lobehub",
        list_url="https://lobehub.com/skills",
        kind="html",
        paging="page",
        rate_limit=(1, 5.0),
        page_size=60,
    ),
    "skills.palebluedot": Platform(
        name="skills.palebluedot",
        parser="skills_palebluedot",
        list_url="https://skills.palebluedot.live/api/skills",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
    ),
    "skillsdirectory": Platform(
        name="skillsdirectory",
        parser="skillsdirectory",
        list_url="https://www.skillsdirectory.com/api/skills",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
    ),
    "skillsmk": Platform(
        name="skillsmk",
        parser="skillsmk",
        list_url="https://skillsmk.com/api/proxy/skills",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
    ),
    "skillszoo": Platform(
        name="skillszoo",
        parser="skillszoo",
        list_url="https://www.skillszoo.com/categories",
        kind="html",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=60,
    ),
    "agnxi": Platform(
        name="agnxi",
        parser="agnxi",
        list_url="https://agnxi.com/api/skills",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
    ),
    "agent-skills.md": Platform(
        name="agent-skills.md",
        parser="agent_skills_md",
        list_url="https://agent-skills.md/api/backfill-metadata",
        paging="single",
        rate_limit=(1, 5.0),
    ),
    "toprankskills": Platform(
        name="toprankskills",
        parser="toprankskills",
        list_url="https://www.toprankskills.com/skill",
        kind="html",
        paging="page",
        rate_limit=(1, 2.0),
        page_size=100,
    ),
    "skillsmp": Platform(
        name="skillsmp",
        parser="skillsmp",
        list_url="https://skillsmp.com/api/v1/skills/search",
        paging="page",
        rate_limit=(1, 1.0),
        page_size=50,
        keyword_param="q",
        keywords=SKILLSMP_KEYWORDS,
        notes="documented public search API; a keyword or creator sweep is mandatory",
    ),
    "skills.rest": Platform(
        name="skills.rest",
        parser="skills_rest_sitemap",
        list_url="https://skills.rest/sitemap-index/{page}.xml",
        kind="xml",
        paging="page",
        rate_limit=(1, 1.0),
        page_size=10000,
        url_template=True,
        detail="skills_rest_detail",
        max_pages=73,
        notes="robots.txt disallows /api/ and every query string, so the published sitemaps are the crawl path",
    ),
    "awesome-agent-skills": Platform(
        name="awesome-agent-skills",
        parser="awesome_agent_skills",
        list_url="https://awesomeagentskills.dev/skills",
        paging="single",
        rate_limit=(1, 5.0),
        notes="single-page dump: the whole catalogue ships in one React flight payload",
    ),
}


def platform_names() -> List[str]:
    return sorted(PLATFORMS)


def get(name: str) -> Platform:
    try:
        return PLATFORMS[name]
    except KeyError as exc:
        raise KeyError(f"unknown platform {name!r}; known: {', '.join(platform_names())}") from exc
