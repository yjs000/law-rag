$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$tempRoot = Join-Path $repoRoot ".data\test-tmp-$PID"
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
$env:TEMP = $tempRoot
$env:TMP = $tempRoot
$env:PYTHONPATH = "$(Join-Path $repoRoot 'apps\api');$(Join-Path $repoRoot 'packages\law-rag-core\src')"

function Assert-LastExitCode {
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

uv run --project packages/law-rag-core pytest packages/law-rag-core/tests
Assert-LastExitCode
uv run --project packages/law-rag-core ruff check packages/law-rag-core
Assert-LastExitCode
uv run --project apps/api pytest apps/api/tests
Assert-LastExitCode
uv run --project apps/api ruff check apps/api/app apps/api/tests apps/api/scripts
Assert-LastExitCode
uv run --project apps/collector pytest apps/collector/tests
Assert-LastExitCode
uv run --project apps/collector ruff check apps/collector/src apps/collector/tests
Assert-LastExitCode
uv run --project apps/api python scripts/check_docs.py
Assert-LastExitCode
pnpm.cmd lint:web
Assert-LastExitCode
pnpm.cmd typecheck
Assert-LastExitCode
pnpm.cmd test
Assert-LastExitCode
pnpm.cmd build
Assert-LastExitCode
