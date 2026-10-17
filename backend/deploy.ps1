# Ship both services' code/config; keep server-native models, data and database credentials.
param(
    [string]$Key = "$env:USERPROFILE\.ssh\linuxone-teammate",
    [string]$Server = "linux1@148.100.77.171",
    [switch]$WorkingTree,
    [switch]$InstallDependencies
)
$ErrorActionPreference = "Stop"
$root = git -C $PSScriptRoot rev-parse --show-toplevel
$tgz = Join-Path $env:TEMP ("tracefront-release-" + [guid]::NewGuid().ToString("N") + ".tgz")
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $python)) { $python = "python" }
$packageArgs = @("-B", (Join-Path $PSScriptRoot "package_release.py"), "--output", $tgz)
if ($WorkingTree) { $packageArgs += "--working-tree" }
elseif (git -C $root status --porcelain -- backend food-risk-ml/src food-risk-ml/configs) {
    Write-Warning "Uncommitted changes are excluded. Use -WorkingTree to deploy the current source without committing."
}
& $python @packageArgs
if ($LASTEXITCODE) { throw "release packaging failed" }
$remoteName = [IO.Path]::GetFileName($tgz)
scp -i $Key $tgz "${Server}:/tmp/$remoteName"
if ($LASTEXITCODE) { throw "release copy failed" }
$skipInstall = if ($InstallDependencies) { "0" } else { "1" }
$remote = @'
set -euo pipefail
cd ~/tracefront
backup=~/tracefront-backups/$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$backup"
chmod 700 "$backup"
shopt -s nullglob
tar --exclude=__pycache__ --exclude='*.pyc' -czf "$backup/code.tgz" backend/app backend/*.py backend/*.sh food-risk-ml/src food-risk-ml/configs
tar -xzf /tmp/RELEASE_FILE -C ~/tracefront
python3 - <<'PY'
import hashlib, json
from pathlib import Path
manifest = json.loads(Path('release-manifest.json').read_text())
for name, expected in manifest['sha256'].items():
    if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
        raise SystemExit('release checksum mismatch: ' + name)
print('release bytes verified:', manifest['revision'], 'working tree:', manifest['working_tree'])
PY
TRACEFRONT_SKIP_INSTALL=__INSTALL_FLAG__ bash backend/setup_linuxone.sh
bash backend/setup_ml_linuxone.sh
~/.venvs/foodrisk/bin/python -B backend/preflight.py
echo "Previous application code saved at $backup/code.tgz"
'@
$remote = $remote.Replace("RELEASE_FILE", $remoteName).Replace("__INSTALL_FLAG__", $skipInstall).Replace("`r`n", "`n")
$remote | ssh -i $Key $Server "bash -s"
if ($LASTEXITCODE) { throw "deployment/preflight failed; check the reported step before presenting" }
