$ErrorActionPreference = "Stop"

uv run --project packages/law-rag-core pytest
uv run --project packages/law-rag-core ruff check packages/law-rag-core
uv run --project apps/api pytest
uv run --project apps/api ruff check apps/api/app apps/api/tests apps/api/scripts
pnpm.cmd typecheck
pnpm.cmd test
pnpm.cmd build

