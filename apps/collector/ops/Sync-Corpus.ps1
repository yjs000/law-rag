param(
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\.."))
)

# Runs the reviewed 3-phase corpus pipeline (prepare-current -> generate-cache -> apply-prepared)
# in one command. This is the manual replacement for the abandoned law-rag-ingestion GitHub
# Actions plan (see docs/design-docs/technology-stack.md decision log) - there is still no
# scheduler, so this must be invoked by hand on the machine with the Open API's registered IP.

$ErrorActionPreference = "Stop"
$collector = Join-Path $RepositoryRoot "apps\collector"
$api = Join-Path $RepositoryRoot "apps\api"
if (-not (Test-Path (Join-Path $collector "pyproject.toml"))) {
    throw "collector 프로젝트를 찾을 수 없습니다: $collector"
}

$runId = Get-Date -Format "yyyyMMddTHHmmssZ"
$bundle = Join-Path $RepositoryRoot ".data\corpus-updates\$runId"

Push-Location $RepositoryRoot
try {
    Write-Host "[1/3] prepare-current -> $bundle"
    & uv run --project apps/collector law-rag-collector prepare-current --output $bundle
    if ($LASTEXITCODE -ne 0) { throw "prepare-current가 종료 코드 $LASTEXITCODE 로 실패했습니다." }

    Write-Host "[2/3] generate-cache (변경된 조문만 임베딩)"
    & uv run --directory apps/api python -m scripts.backfill_embeddings generate-cache --bundle $bundle
    if ($LASTEXITCODE -ne 0) { throw "generate-cache가 종료 코드 $LASTEXITCODE 로 실패했습니다." }

    Write-Host "[3/3] apply-prepared (운영 반영)"
    & uv run --project apps/collector law-rag-collector apply-prepared --bundle $bundle
    if ($LASTEXITCODE -ne 0) { throw "apply-prepared가 종료 코드 $LASTEXITCODE 로 실패했습니다." }

    Write-Host "완료: $bundle"
}
finally {
    Pop-Location
}
