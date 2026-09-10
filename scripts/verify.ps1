$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonRunner = Join-Path $repoRoot "scripts\run_python.ps1"

function Assert-LastExitCode {
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Invoke-WorkspacePython {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $pythonRunner @args
    Assert-LastExitCode
}

Invoke-WorkspacePython -m pytest -p no:cacheprovider packages/law-rag-core/tests
Invoke-WorkspacePython -m ruff check packages/law-rag-core
Push-Location apps/api
try {
    Invoke-WorkspacePython -m pytest -p no:cacheprovider tests
}
finally {
    Pop-Location
}
Invoke-WorkspacePython -m ruff check apps/api/app apps/api/tests apps/api/scripts
Invoke-WorkspacePython -m pytest -p no:cacheprovider apps/collector/tests
Invoke-WorkspacePython -m ruff check apps/collector/src apps/collector/tests
Invoke-WorkspacePython scripts/check_docs.py
Invoke-WorkspacePython scripts/check_roadmap.py
pnpm.cmd lint:web
Assert-LastExitCode
pnpm.cmd typecheck
Assert-LastExitCode
pnpm.cmd test
Assert-LastExitCode
pnpm.cmd build
Assert-LastExitCode
