---
name: frontend-design
description: Generate production-ready frontend components from a design brief and export them as a component bundle.
license: MIT
allowed-tools: Read, Write, Bash
---

# Frontend Design

Turn a design brief into a component bundle.

## Workflow

1. Read the brief and extract the component inventory.
2. Render each component from the templates in `assets/`.
3. Run `scripts/render.py` to bundle the result.

## Boundaries

- Never modify files outside the output directory.
- Ask for confirmation before running a build.
