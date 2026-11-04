# Build the RFID operator package with Nuitka on Windows (CI: windows-latest).
# ONE exe with roles: supervisor / --role api / --selftest / --stop.
# usage:  powershell -File packaging\build_nuitka_windows.ps1 [-Tag v1.2.3]
param([string]$Tag = "dev")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$ExeName = "Activerse RFID"
python -m pip install -q -U pip wheel
python -m pip install -q -r requirements-packaging.txt
python -m pip install -q -r requirements.txt

Push-Location frontend
npm ci --silent
npm run build
Pop-Location

$Out = Join-Path $Root "dist\nuitka"
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force $Out | Out-Null

$env:PYTHONPATH = "$Root"

# mysql.connector is only imported when MYSQL_HOST is set (not in requirements): never bundle.
$NoFollow = @("tkinter","numpy","PIL","cv2","mysql","pytest","tests")
$NuitkaArgs = @(
  "--standalone", "--assume-yes-for-downloads",
  "--output-dir=$Out", "--output-filename=$ExeName",
  "--include-package=api", "--include-package=floor_launcher",
  "--include-package=fastapi", "--include-package=starlette", "--include-package=uvicorn",
  "--include-package=pydantic", "--include-package=pydantic_core",
  "--include-package=httpx", "--include-package=httpcore", "--include-package=anyio",
  "--include-package=h11", "--include-package=idna", "--include-package=annotated_types",
  "--include-package=certifi", "--include-package-data=certifi",
  "--include-package=loguru", "--include-package=dotenv",
  "--include-package=openpyxl", "--include-package=et_xmlfile",
  "--include-package=multipart", "--include-package=python_multipart",
  "--include-module=sqlite3"
)
foreach ($m in $NoFollow) { $NuitkaArgs += "--nofollow-import-to=$m" }
$NuitkaArgs += "floor_launcher/entry.py"

python -m nuitka @NuitkaArgs
if ($LASTEXITCODE -ne 0) { throw "Nuitka failed" }

$Stage = Join-Path $Root "dist\release\Activerse-RFID-$Tag-windows"
python packaging/stage_release.py $Stage (Join-Path $Out "entry.dist") --windows
if ($LASTEXITCODE -ne 0) { throw "staging failed" }

$Zip = "$Stage-nuitka.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path $Stage -DestinationPath $Zip
Write-Host "Wrote $Zip"
