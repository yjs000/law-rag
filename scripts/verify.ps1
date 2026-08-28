$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
function Resolve-TestTempParent {
    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_TEST_TEMP_ROOT)) {
        return $env:CODEX_TEST_TEMP_ROOT
    }

    if ($env:CODEX_SESSION_ID -and $env:USERPROFILE) {
        $visualizationsRoot = Join-Path $env:USERPROFILE ".codex\visualizations"
        if (Test-Path $visualizationsRoot) {
            $sessionDirectory = Get-ChildItem -Path $visualizationsRoot -Directory -Recurse -Filter $env:CODEX_SESSION_ID -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($sessionDirectory) {
                return $sessionDirectory.FullName
            }
        }
    }

    return (Join-Path $repoRoot ".data")
}

$tempParent = Resolve-TestTempParent
$tempRoot = Join-Path $tempParent "test-tmp-$PID"
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
$corePytestTemp = Join-Path $tempRoot "pytest-core"
$apiPytestTemp = Join-Path $tempRoot "pytest-api"
$collectorPytestTemp = Join-Path $tempRoot "pytest-collector"
$env:TEMP = $tempRoot
$env:TMP = $tempRoot
$env:PYTHONPATH = "$(Join-Path $repoRoot 'apps\api');$(Join-Path $repoRoot 'packages\law-rag-core\src')"

function Assert-LastExitCode {
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

uv run --project packages/law-rag-core python -m pytest --basetemp $corePytestTemp packages/law-rag-core/tests
Assert-LastExitCode
uv run --project packages/law-rag-core ruff check packages/law-rag-core
Assert-LastExitCode
Push-Location apps/api
try {
    uv run --project . python -m pytest --basetemp $apiPytestTemp tests
    Assert-LastExitCode
}
finally {
    Pop-Location
}
uv run --project apps/api ruff check apps/api/app apps/api/tests apps/api/scripts
Assert-LastExitCode
uv run --project apps/collector python -m pytest --basetemp $collectorPytestTemp apps/collector/tests
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
