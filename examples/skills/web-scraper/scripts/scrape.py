# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Example Author
"""Fetch a page and return the article body."""

import re
import urllib.request

RE_TAG = re.compile(r"<[^>]+>")


def scrape(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        html = response.read().decode("utf-8", errors="ignore")
    return RE_TAG.sub("", html).strip()
