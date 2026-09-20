param(
    [switch]$SkipSync,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host '[1/8] Synchronizing the uv environment...'
if (-not $SkipSync) {
    uv sync --extra build
    if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }
}

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw "Python environment not found: $Python" }

Write-Host '[2/8] Building browser resources...'
node src/node/build.mjs
if ($LASTEXITCODE -ne 0) { throw 'Browser resource build failed.' }

if (-not $SkipTests) {
    Write-Host '[3/8] Running Python and viewer tests...'
    $env:PYTHONPATH = 'src'
    & $Python -m unittest discover -s tests -p 'test_*.py' -v
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    node --test tests/node.test.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Viewer tests failed.' }
} else {
    Write-Host '[3/8] Tests skipped by request.'
}

Write-Host '[4/8] Building the Windows application...'
$Dist = Join-Path $Root 'dist-portable'
$Work = Join-Path $Root '.build\pyinstaller'
Remove-Item $Dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue
& $Python -m PyInstaller packaging\IFC_HTML_Generator.spec --noconfirm --clean --distpath $Dist --workpath $Work
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$App = Join-Path $Dist 'IFC HTML Generator'
Write-Host '[5/8] Adding the private Node.js runtime...'
$Node = (Get-Command node -ErrorAction Stop).Source
$Runtime = Join-Path $App 'runtime'
New-Item $Runtime -ItemType Directory -Force | Out-Null
Copy-Item $Node (Join-Path $Runtime 'node.exe') -Force

Write-Host '[6/8] Adding documentation and notices...'
Copy-Item 'packaging\PORTABLE_README.txt' (Join-Path $App 'README.txt') -Force
Copy-Item 'LICENSE' (Join-Path $App 'LICENSE.txt') -Force
$Licenses = Join-Path $App 'LICENSES'
New-Item $Licenses -ItemType Directory -Force | Out-Null
Copy-Item 'packaging\licenses\NODE_LICENSE.txt' (Join-Path $Licenses 'NODE_LICENSE.txt') -Force
Copy-Item 'node_modules\three\LICENSE' (Join-Path $Licenses 'THREE_LICENSE.txt') -Force
Copy-Item 'node_modules\web-ifc\LICENSE.md' (Join-Path $Licenses 'WEB_IFC_LICENSE.md') -Force
Copy-Item 'node_modules\@thatopen\fragments\node_modules\pako\LICENSE' (Join-Path $Licenses 'PAKO_LICENSE.txt') -Force
$IfcMetadata = Get-ChildItem '.venv\Lib\site-packages\ifcopenshell-*.dist-info\METADATA' | Select-Object -First 1
if ($IfcMetadata) { Copy-Item $IfcMetadata.FullName (Join-Path $Licenses 'IFCOPENSHELL_METADATA.txt') -Force }

Write-Host '[7/8] Testing packaged resources...'
$Exe = Join-Path $App 'IFC HTML Generator.exe'
& $Exe --self-test
if ($LASTEXITCODE -ne 0) { throw 'Packaged resource self-test failed.' }

Write-Host '[8/8] Reporting portable build...'
$Files = Get-ChildItem $App -Recurse -File
$Bytes = ($Files | Measure-Object Length -Sum).Sum
Write-Host "Portable application: $App"
Write-Host "Files: $($Files.Count)"
Write-Host ("Size: {0:N0} bytes" -f $Bytes)
