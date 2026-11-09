# Sync project Knowledge Graph with latest codebase changes
param (
    [switch]$Clean = $false
)

$repoRoot = Split-Path -Parent $PSScriptRoot

if ($Clean) {
    Write-Host "Rebuilding knowledge graph cleanly for: $repoRoot" -ForegroundColor Yellow
    cgr start --repo-path "$repoRoot" --clean --yes --update-graph
} else {
    Write-Host "Updating knowledge graph for: $repoRoot" -ForegroundColor Cyan
    cgr start --repo-path "$repoRoot" --update-graph
}

Write-Host "`nCurrent Knowledge Graph Statistics:" -ForegroundColor Green
cgr stats --repo-path "$repoRoot"
