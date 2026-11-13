---
name: data-connector
description: Connect to an SQL warehouse, run a query and return the result as structured rows.
license: Apache 2.0 / MIT
---

# Data Connector

## Workflow

1. Read the connection string from the environment.
2. Run `scripts/fetch.py` with the query.
3. Return the rows as JSON.
