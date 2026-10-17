# Deploys the last commit's backend/ to the LinuxONE server: packs it, copies it, and setup_linuxone.sh installs
# anything missing and restarts the API. Database data is kept. Run from anywhere: .\backend\deploy.ps1
param(
    [string]$Key = "$env:USERPROFILE\.ssh\linuxone-teammate",
    [string]$Server = "linux1@148.100.77.171"
)
$ErrorActionPreference = "Stop"
$root = git -C $PSScriptRoot rev-parse --show-toplevel
$tgz = Join-Path $env:TEMP "tracefront-backend.tgz"

if (git -C $root status --porcelain -- backend ':!*__pycache__*') {
    Write-Warning "backend/ has uncommitted changes; they are NOT deployed, only the last commit is."
}
Write-Host "Deploying $(git -C $root rev-parse --abbrev-ref HEAD): $(git -C $root log -1 --format='%h %s')"

# Archive from the root so the root .gitattributes applies (*.sh stays LF for bash)
git -C $root archive --format=tar.gz -o $tgz HEAD backend
if ($LASTEXITCODE) { throw "git archive failed" }
scp -i $Key $tgz "${Server}:/tmp/tracefront-backend.tgz"
if ($LASTEXITCODE) { throw "copy to $Server failed" }
ssh -i $Key $Server "tar -xzf /tmp/tracefront-backend.tgz -C ~/tracefront && bash ~/tracefront/backend/setup_linuxone.sh"
if ($LASTEXITCODE) { throw "setup on $Server failed" }
