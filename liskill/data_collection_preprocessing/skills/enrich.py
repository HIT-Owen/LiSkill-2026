"""Data enrichment (§3.1.1) and the GitHub side of the extraction scope (§3.2.1).

For every unique skill the pipeline keeps three physical anchors:

* ``skill_file_path`` — the skill release package (SKILL.md + scripts/ + ...),
* ``file_path`` — the ZIP archive of the associated GitHub repository,
* ``repo_license`` — the repository-level license reported by the GitHub API.

The repository license is what the Repository level of §3.2.1 reads, and the
package archive is what the Component level scans.  Nothing here is required by
the offline demo: every method is a no-op when no token / network is available.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .http import HttpClient
from .spiders import github_full_name

GITHUB_API = "https://api.github.com"


@dataclass
class EnrichmentResult:
    repo_license: Optional[str] = None
    skill_md_content: str = ""
    skill_file_path: Optional[str] = None
    file_path: Optional[str] = None
    default_branch: Optional[str] = None


class GitHubEnricher:
    """Fetches the repository license and the skill package contents."""

    def __init__(
        self,
        http: Optional[HttpClient] = None,
        token: Optional[str] = None,
        cache_dir: Optional[str | Path] = None,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.http = http or HttpClient(headers=headers)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ metadata
    def repository(self, full_name: str) -> Dict[str, object]:
        payload = self.http.get(f"{GITHUB_API}/repos/{full_name}")
        return json.loads(payload)

    def repo_license(self, full_name: str) -> Optional[str]:
        """``repo_license`` of Table 4: the SPDX id of the repository license."""
        try:
            data = self.repository(full_name)
        except RuntimeError:
            return None
        license_info = data.get("license") or {}
        return license_info.get("spdx_id") if isinstance(license_info, dict) else None

    def default_branch(self, full_name: str) -> Optional[str]:
        try:
            return str(self.repository(full_name).get("default_branch") or "") or None
        except RuntimeError:
            return None

    # ------------------------------------------------------------------ content
    def skill_md(
        self, full_name: str, relative_path: str, branch: str = "main"
    ) -> str:
        path = f"{relative_path}/SKILL.md" if relative_path else "SKILL.md"
        url = f"https://raw.githubusercontent.com/{full_name}/{branch}/{path}"
        try:
            return self.http.get(url)
        except RuntimeError:
            return ""

    def download_repo_zip(self, full_name: str, branch: str = "") -> Optional[bytes]:
        suffix = f"/{branch}" if branch else ""
        url = f"{GITHUB_API}/repos/{full_name}/zipball{suffix}"
        try:
            raw = self.http.get(url)
        except RuntimeError:
            return None
        return raw.encode("utf-8", errors="ignore")

    def extract_component_files(
        self, full_name: str, relative_path: str, branch: str = "main", limit: int = 200
    ) -> List[Dict[str, str]]:
        """Return ``[{path, head}]`` for the files of one skill (component scan)."""
        url = f"{GITHUB_API}/repos/{full_name}/git/trees/{branch}?recursive=1"
        try:
            data = json.loads(self.http.get(url))
        except (RuntimeError, json.JSONDecodeError):
            return []
        prefix = f"{relative_path.strip('/')}/" if relative_path else ""
        files: List[Dict[str, str]] = []
        for item in data.get("tree", []):
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if prefix and not path.startswith(prefix):
                continue
            if not path.lower().endswith(
                (".py", ".sh", ".js", ".ts", ".go", ".java", ".rs", ".md")
            ):
                continue
            files.append({"path": path[len(prefix) :], "sha": item.get("sha", "")})
            if len(files) >= limit:
                break
        return files


def read_skill_md_from_zip(payload: bytes) -> str:
    """Read ``SKILL.md`` out of a repository or skill archive."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (zipfile.BadZipFile, OSError):
        return ""
    for name in archive.namelist():
        if name.lower().endswith("skill.md"):
            try:
                return archive.read(name).decode("utf-8", errors="ignore")
            except KeyError:  # pragma: no cover - defensive
                continue
    return ""


def attach_repo_metadata(record: Dict[str, object], enricher: GitHubEnricher) -> Dict[str, object]:
    """Fill ``repo_license`` / ``default_branch`` for one collected record."""
    full_name = str(record.get("repo_full_name") or github_full_name(str(record.get("repo_url") or "")))
    if not full_name:
        return record
    record = dict(record)
    record.setdefault("repo_full_name", full_name)
    if not record.get("repo_license"):
        record["repo_license"] = enricher.repo_license(full_name)
    if not record.get("default_branch"):
        record["default_branch"] = enricher.default_branch(full_name) or "main"
    return record
