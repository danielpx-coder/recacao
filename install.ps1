# PowerShell Script de Instalação e Execução Portátil
# Danaurium Redação Studio para Windows 10 e 11
# Execução: powershell -ExecutionPolicy Bypass -File .\install.ps1

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Instalação Portátil — Danaurium Redação Studio" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$AppDataDir = "$env:LOCALAPPDATA\DanauriumRedacaoStudio"
Write-Host "`n[1] Verificando diretórios locais em $AppDataDir..." -ForegroundColor Yellow

$folders = @("database", "config", "cache", "logs", "backups", "exports", "sample_data")
foreach ($folder in $folders) {
    $targetPath = Join-Path $AppDataDir $folder
    if (-not (Test-Path $targetPath)) {
        New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
        Write-Host "    • Criado: $folder" -ForegroundColor Green
    }
}

Write-Host "`n[2] Copiando matérias de exemplo..." -ForegroundColor Yellow
if (Test-Path "sample_data") {
    Copy-Item -Path "sample_data\*" -Destination "$AppDataDir\sample_data" -Recurse -Force
    Write-Host "    • Matérias de exemplo copiadas para $AppDataDir\sample_data" -ForegroundColor Green
}

Write-Host "`n[3] Verificando execução..." -ForegroundColor Yellow
if (Test-Path "dist\DanauriumRedacaoStudio\DanauriumRedacaoStudio.exe") {
    Write-Host "    • Executável compilado encontrado em dist\DanauriumRedacaoStudio." -ForegroundColor Green
    Write-Host "    • Iniciando o Danaurium Redação Studio..." -ForegroundColor Cyan
    Start-Process "dist\DanauriumRedacaoStudio\DanauriumRedacaoStudio.exe"
} else {
    Write-Host "    • Executável compilado não encontrado em dist." -ForegroundColor Yellow
    Write-Host "    • Iniciando via interpretador Python local..." -ForegroundColor Cyan
    python -m danaurium.app
}

Write-Host "`nInstalação concluída com sucesso!" -ForegroundColor Green
