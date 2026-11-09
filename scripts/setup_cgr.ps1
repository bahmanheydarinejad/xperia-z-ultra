# Setup Code-Graph-RAG for xperia-z-ultra
# Requires PowerShell and Python 3.12+

$ErrorActionPreference = "Stop"

Write-Host "=== Code-Graph-RAG Setup for xperia-z-ultra ===" -ForegroundColor Cyan

# 1. Locate Python 3.12+
$pythonCmd = $null
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $ver = python --version 2>&1
    if ($ver -match "Python 3\.(1[2-9]|[2-9][0-9])") {
        $pythonCmd = "python"
    }
}

if (-not $pythonCmd) {
    $py312Path = "C:\Users\parse-it\AppData\Local\Programs\Python\Python312\python.exe"
    if (Test-Path $py312Path) {
        $pythonCmd = $py312Path
    }
}

if (-not $pythonCmd) {
    Write-Error "Python 3.12+ is required for Code-Graph-RAG but could not be located."
    exit 1
}

Write-Host "Using Python: $pythonCmd" -ForegroundColor Green

# 2. Install Code-Graph-RAG with Tree-sitter and AST-Grep support
Write-Host "Installing code-graph-rag[treesitter-full,ast-grep]..." -ForegroundColor Cyan
& $pythonCmd -m pip install --upgrade "code-graph-rag[treesitter-full,ast-grep]"

# 3. Check Ripgrep (rg)
if (-not (Get-Command "rg" -ErrorAction SilentlyContinue)) {
    Write-Host "ripgrep (rg) not found in PATH. Checking WinGet..." -ForegroundColor Yellow
    if (Get-Command "winget" -ErrorAction SilentlyContinue) {
        winget install --id BurntSushi.ripgrep.MSVC --exact --accept-source-agreements --accept-package-agreements
    }
}

# 4. Verify cgr executable
$repoRoot = Split-Path -Parent $PSScriptRoot
Write-Host "Generating initial knowledge graph for repository: $repoRoot" -ForegroundColor Cyan
cgr start --repo-path "$repoRoot" --update-graph

Write-Host "Displaying graph statistics..." -ForegroundColor Cyan
cgr stats --repo-path "$repoRoot"

Write-Host "=== Code-Graph-RAG setup complete! ===" -ForegroundColor Green
