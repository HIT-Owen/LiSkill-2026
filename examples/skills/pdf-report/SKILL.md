---
name: pdf-report
description: Render a structured data set into a paginated PDF report with charts and a table of contents.
license: Proprietary. LICENSE.txt has complete terms
---

# PDF Report

## Workflow

1. Validate the input data set against `references/schema.md`.
2. Render charts with `scripts/chart.py`.
3. Assemble the PDF with `scripts/build_pdf.py`.

## Boundaries

- Do not embed external images.
