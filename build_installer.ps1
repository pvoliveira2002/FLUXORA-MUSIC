param(
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$InnoCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
)
$InnoCompiler = $InnoCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Ambiente virtual ausente. Execute instalar.bat primeiro.'
}
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    throw 'Node.js 22 ou superior é necessário somente para gerar o instalador.'
}
if (-not $InnoCompiler) {
    throw 'Inno Setup 6 não encontrado. Instale com: winget install JRSoftware.InnoSetup'
}

if (-not $SkipTests) {
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Os testes falharam; a distribuição não será criada.' }
}

& $Python -m pip install --disable-pip-version-check -r requirements.txt -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Falha ao verificar dependências de build.' }

& $Python -m PyInstaller --noconfirm --clean Fluxora.spec
if ($LASTEXITCODE -ne 0) { throw 'Falha ao empacotar o Fluxora.' }

& $InnoCompiler (Join-Path $ProjectRoot 'installer\Fluxora.iss')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o instalador.' }

$Installer = Join-Path $ProjectRoot 'dist\installer\Fluxora-Setup-3.2.0.exe'
if (-not (Test-Path -LiteralPath $Installer)) { throw 'O instalador não foi encontrado após a compilação.' }
$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Installer).Hash
Write-Host "`nInstalador concluído: $Installer"
Write-Host "SHA-256: $Hash"
