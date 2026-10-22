param()
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    python -m PyInstaller --noconfirm --clean ConferenceDirector.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
} finally {
    Pop-Location
}
