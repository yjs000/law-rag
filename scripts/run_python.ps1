$ErrorActionPreference = "Stop"
$PythonArguments = @($args)

if (-not $PythonArguments -or $PythonArguments.Count -eq 0) {
    throw "Pass Python arguments, for example: scripts/run_python.ps1 -m pytest"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspacePython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $workspacePython -PathType Leaf)) {
    throw "Workspace Python is unavailable at $workspacePython"
}

$sourceRoots = @(
    (Join-Path $repoRoot "apps\api")
    (Join-Path $repoRoot "apps\collector\src")
    (Join-Path $repoRoot "apps\law-rag-llamaindex\src")
    (Join-Path $repoRoot "packages\law-rag-core\src")
)
$existingPaths = @($env:PYTHONPATH -split ";" | Where-Object { $_ })
$env:PYTHONPATH = [string]::Join(";", @($sourceRoots + $existingPaths | Select-Object -Unique))
$env:PYTHONUTF8 = "1"
$env:RUFF_CACHE_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "law-rag-ruff-cache-$PID"

& $workspacePython @PythonArguments
exit $LASTEXITCODE
