---
name: web-scraper
description: Fetch a page, extract the article body and return it as clean Markdown.
---

# Web Scraper

## Workflow

1. Fetch the page with `scripts/scrape.py`.
2. Strip navigation and advertisement blocks.
3. Return the article body as Markdown.

## Notes

The skill ships no license field on purpose: the only declaration lives in the
head comment of `scripts/scrape.py`, so the Component level is the single
carrier of the license.
