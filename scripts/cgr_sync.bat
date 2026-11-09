@echo off
set REPO_ROOT=%~dp0..
echo Updating Code-Graph-RAG Knowledge Graph for %REPO_ROOT%...
cgr start --repo-path "%REPO_ROOT%" --update-graph
if %ERRORLEVEL% NEQ 0 (
    echo Error updating graph!
    exit /b %ERRORLEVEL%
)
cgr stats --repo-path "%REPO_ROOT%"
echo Graph update complete.
