"""Truncated sample payloads per platform.

Stored so that the parsers can be exercised (and tested) without touching the
network: the shapes are the ones the live endpoints returned when the
collectors were written, trimmed to two items each.  They are deliberately
small and are **not** research data.
"""

from __future__ import annotations

import json
from typing import Dict, List

FIXTURES: Dict[str, List[str]] = {
    "clawhub": [
        json.dumps(
            {
                "items": [
                    {
                        "slug": "frontend-design",
                        "summary": "Generate production-ready frontend components.",
                        "ownerHandle": "example-author",
                        "tags": {"latest": "1.2.0"},
                        "repository": "https://github.com/example/frontend-design",
                    },
                    {
                        "slug": "pdf-report",
                        "summary": "Render a paginated PDF report from structured data.",
                        "ownerHandle": "example-corp",
                        "tags": {"latest": "0.4.1"},
                        "repository": "",
                    },
                ]
            },
            ensure_ascii=False,
        )
    ],
    "agentskills.in": [
        json.dumps(
            {
                "total": 2,
                "limit": 100,
                "offset": 0,
                "skills": [
                    {
                        "name": "data-connector",
                        "description": "Run a query against an SQL warehouse and return rows.",
                        "author": "example-author",
                        "githubUrl": "https://github.com/example/data-connector",
                    },
                    {
                        "name": "web-scraper",
                        "description": "Fetch a page and return the article body as Markdown.",
                        "author": "example-author",
                        "githubUrl": "https://github.com/example/web-scraper/tree/main/skills/scrape",
                    },
                ],
            },
            ensure_ascii=False,
        )
    ],
    "skills.lc": [
        json.dumps(
            {
                "data": {
                    "pagination": {"page": 1, "totalPages": 2},
                    "skills": [
                        {
                            "name": "changelog-writer",
                            "description": "Summarise merged pull requests into a changelog.",
                            "author": "example-author",
                            "githubUrl": "https://github.com/example/changelog-writer",
                        }
                    ],
                }
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "data": {
                    "pagination": {"page": 2, "totalPages": 2},
                    "skills": [
                        {
                            "name": "k8s-deploy",
                            "description": "Deploy a container image and verify the rollout.",
                            "author": "example-ops",
                            "githubUrl": "https://github.com/example/k8s-deploy/tree/main/skill",
                        }
                    ],
                }
            },
            ensure_ascii=False,
        ),
    ],
    "skills.sh": [
        json.dumps(
            {
                "total": 2,
                "hasMore": False,
                "page": 0,
                "skills": [
                    {
                        "name": "seo-audit",
                        "description": "Audit a page for SEO issues.",
                        "source": "example/example-skills",
                    },
                    {
                        "name": "image-optimizer",
                        "description": "Compress and convert images to modern formats.",
                        "source": "example/image-tools",
                    },
                ],
            },
            ensure_ascii=False,
        )
    ],
    "skillmaps": [
        json.dumps(
            {
                "items": [
                    {
                        "name": "unit-test-gen",
                        "description": "Generate unit tests for untested functions.",
                        "github_url": "https://github.com/example/unit-test-gen",
                    }
                ],
                "page": 1,
                "totalPages": 1,
            },
            ensure_ascii=False,
        )
    ],
    "smithery": [
        json.dumps(
            {
                "pagination": {"currentPage": 1, "totalPages": 1},
                "skills": [
                    {
                        "slug": "slack-notifier",
                        "description": "Send structured notifications to Slack.",
                        "owner": "example",
                        "gitUrl": "https://github.com/example/slack-notifier",
                    }
                ],
            },
            ensure_ascii=False,
        )
    ],
    "lobehub": [
        '{"data":\\"[{\\"identifier\\":\\"invoice-parser\\",\\"name\\":\\"Invoice Parser\\",'
        '\\"description\\":\\"Extract line items from a PDF invoice.\\",'
        '\\"homepage\\":\\"https://github.com/example/invoice-parser\\"}]\\"],\\"total\\":1}',
    ],
    "skills.palebluedot": [
        json.dumps(
            {
                "pagination": {"page": 1, "totalPages": 1},
                "skills": [
                    {
                        "name": "video-transcriber",
                        "description": "Transcribe audio and produce a timestamped transcript.",
                        "githubOwner": "example",
                        "githubRepo": "media-tools",
                        "skillPath": "skills/transcriber",
                    }
                ],
            },
            ensure_ascii=False,
        )
    ],
    "skillsdirectory": [
        json.dumps(
            {
                "pagination": {"page": 1, "totalPages": 1},
                "skills": [
                    {
                        "name": "csv-cleaner",
                        "description": "Normalise a messy CSV into a tidy table.",
                        "author": "example",
                        "sourceUrl": "https://github.com/example/csv-cleaner",
                        "skillFilePath": "https://github.com/example/csv-cleaner/blob/main/skill/SKILL.md",
                    }
                ],
            },
            ensure_ascii=False,
        )
    ],
    "skillsmk": [
        json.dumps(
            {
                "meta": {"current_page": 1, "last_page": 1},
                "data": [
                    {
                        "name": "prompt-linter",
                        "description": "Lint an LLM prompt for ambiguity.",
                        "repo_full_name": "example/prompt-tools",
                        "skill_path": "skills/linter",
                    }
                ],
            },
            ensure_ascii=False,
        )
    ],
    "skillszoo": [
        '{"categorySkills":\\"[{\\"name\\":\\"api-mocker\\",'
        '\\"description\\":\\"Generate a mock server from an OpenAPI spec.\\",'
        '\\"githubUrl\\":\\"https://github.com/example/api-mocker\\"}]\\",\\"totalStars\\":12}',
    ],
    "agnxi": [
        json.dumps(
            {
                "page": 1,
                "totalPages": 1,
                "skills": [
                    {
                        "name": "skill-auditor",
                        "description": "Review a skill package for missing metadata.",
                        "author": "example",
                        "url": "https://github.com/example/skill-auditor/blob/main/skill/SKILL.md",
                        "path": "https://github.com/example/skill-auditor/tree/main/skill",
                    }
                ],
            },
            ensure_ascii=False,
        )
    ],
    "agent-skills.md": [
        json.dumps(
            {
                "results": [
                    {
                        "name": "changelog-writer",
                        "description": "Summarise merged pull requests into a changelog.",
                        "author": "example",
                        "repoUrl": "https://github.com/example/changelog-writer",
                    }
                ],
                "skills": ["changelog-writer"],
            },
            ensure_ascii=False,
        )
    ],
    "toprankskills": [
        '<div class="skill-card">'
        '<div class="text-lg">frontend-design</div>'
        '<div class="line-clamp-2">Generate production-ready frontend components.</div>'
        '<div class="gap-2"><a href="https://www.toprankskills.com/skill/frontend-design">detail</a>'
        '<a href="https://github.com/example/frontend-design">github</a></div>'
        "</div>"
    ],
    "skillsmp": [
        json.dumps(
            {
                "success": True,
                "data": {
                    "skills": [
                        {
                            "id": "example-data-connector-skill-md",
                            "name": "data-connector",
                            "author": "example",
                            "description": "Run a query against an SQL warehouse and return rows.",
                            "contentLanguage": "en",
                            "githubUrl": "https://github.com/example/data-connector/tree/main/skills/data-connector",
                            "skillUrl": "https://skillsmp.com/creators/example/data-connector",
                            "stars": 12,
                            "updatedAt": 1779015027,
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "limit": 50,
                        "total": 1,
                        "totalPages": 1,
                        "hasNext": False,
                        "hasPrev": False,
                        "totalIsExact": True,
                    },
                    "filters": {"search": "sql", "sortBy": "stars"},
                },
                "meta": {"requestId": "fixture", "responseTimeMs": 1},
            },
            ensure_ascii=False,
        )
    ],
    "skills.rest": [
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://skills.rest/skill/web-scraper</loc></url>"
        "<url><loc>https://skills.rest/repo/example/web-scraper</loc></url>"
        "</urlset>"
    ],
    "awesome-agent-skills": [
        "<html><body><script>self.__next_f.push([1,"
        + json.dumps(
            '6:["$","$1","c",{"children":[["$","h1",null,{"children":"Browse Skills"}],'
            '["$","$L9",null,{"skills":'
            '[{"id":"example/web-scraper","name":"example/web-scraper",'
            '"description":"Fetch a page and return the article body as Markdown.",'
            '"url":"https://github.com/example/web-scraper","category":"mcp-server",'
            '"platforms":["claude-code"],"source":"fixture","section":"tools",'
            '"githubOwner":"example","githubRepo":"web-scraper","stars":395,'
            '"lastUpdated":"2026-03-13T06:10:48.491Z","repoUrl":"$undefined",'
            '"version":"$undefined","downloads":null}]}]}]'
        )
        + "])</script></body></html>"
    ],
}
