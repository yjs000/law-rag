param(
    [ValidateSet("sync-current", "sync-history", "status")]
    [string]$Command = "sync-history",
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\.."))
)

$ErrorActionPreference = "Stop"
$collector = Join-Path $RepositoryRoot "apps\collector"
if (-not (Test-Path (Join-Path $collector "pyproject.toml"))) {
    throw "collector 프로젝트를 찾을 수 없습니다: $collector"
}

Push-Location $RepositoryRoot
try {
    & uv run --project apps/collector law-rag-collector $Command
    if ($LASTEXITCODE -ne 0) {
        throw "collector가 종료 코드 $LASTEXITCODE 로 실패했습니다."
    }
}
finally {
    Pop-Location
}
