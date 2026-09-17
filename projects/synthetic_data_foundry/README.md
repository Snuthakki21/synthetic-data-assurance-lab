# Application adapter

This directory exposes the `synthetic_data_foundry` application to the command line, browser worker and read-only MCP tools. `project.py` declares the scenario catalog and delegates execution to `app.application.product.ProductApplication`; domain behavior lives in `app/domain` and AI/evaluation components in `app/ai`.

See the [product guide](../../README.md), [architecture](../../docs/ARCHITECTURE.md), [workspace operations](../../docs/WORKSPACE.md), and [independent expanded-source review](../../docs/STAFF_REVIEW_V2.md). Fixtures, when present, are original synthetic inputs and are packaged with the application.
