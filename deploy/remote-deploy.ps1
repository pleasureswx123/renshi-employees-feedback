param([string]$Server = 'root@192.168.10.122', [switch]$WorkingTree, [switch]$PackageOnly)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '../ruoyi-fastapi-backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
$arguments = @((Join-Path $PSScriptRoot 'remote_deploy.py'), '--server', $Server)
if ($WorkingTree) { $arguments += '--working-tree' }
if ($PackageOnly) { $arguments += '--package-only' }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "部署未完成，退出码：$LASTEXITCODE；请检查上述日志。" }
