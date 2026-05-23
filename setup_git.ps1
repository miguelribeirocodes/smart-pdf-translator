# Setup do git para o projeto Tradutor PDF
# Repo: https://github.com/miguelribeirocodes/smart-pdf-translator
#
# Uso (no PowerShell, dentro da pasta do projeto):
#   .\setup_git.ps1
#
# Se aparecer erro "execution policy", rode antes:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"

$REPO_URL = "https://github.com/miguelribeirocodes/smart-pdf-translator.git"

Write-Host "==> Limpando .git parcial criado pelo sandbox..." -ForegroundColor Cyan
if (Test-Path ".git") {
    Get-ChildItem -Path ".git" -Recurse -Force | ForEach-Object {
        try { $_.Attributes = "Normal" } catch {}
    }
    Remove-Item -Path ".git" -Recurse -Force
    Write-Host "   .git removido." -ForegroundColor Green
} else {
    Write-Host "   Nenhum .git para remover." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==> Conferindo user.name e user.email globais..." -ForegroundColor Cyan
$userName = git config --global user.name
$userEmail = git config --global user.email

if (-not $userName -or -not $userEmail) {
    Write-Host "   user.name/user.email NAO configurados." -ForegroundColor Yellow
    $resp = Read-Host "Configurar com 'Miguel Ribeiro' / 'miguelribeiro.dev1@gmail.com'? (s/N)"
    if ($resp -eq "s" -or $resp -eq "S") {
        git config --global user.name "Miguel Ribeiro"
        git config --global user.email "miguelribeiro.dev1@gmail.com"
        Write-Host "   Configurado." -ForegroundColor Green
    } else {
        Write-Host "   OK, configure manualmente e rode este script de novo." -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "   user.name:  $userName" -ForegroundColor Green
    Write-Host "   user.email: $userEmail" -ForegroundColor Green
}

Write-Host ""
Write-Host "==> Inicializando repositorio..." -ForegroundColor Cyan
git init -b main

Write-Host ""
Write-Host "==> Adicionando arquivos..." -ForegroundColor Cyan
git add .

Write-Host ""
Write-Host "==> Status antes do commit:" -ForegroundColor Cyan
git status --short

Write-Host ""
Write-Host "==> Primeiro commit (Fase 0)..." -ForegroundColor Cyan
git commit -m "Fase 0: estrutura inicial + pipeline core" `
    -m "" `
    -m "- Briefing completo (briefing-tradutor-pdf.md)" `
    -m "- Save state vivo (PROGRESSO.md)" `
    -m "- src/extractor.py: extracao de spans com PyMuPDF" `
    -m "- src/translator.py: wrapper Google/MyMemory com cache e fallback" `
    -m "- src/writer.py: reescrita in-place com reducao automatica" `
    -m "- src/pipeline.py: orquestrador com callback de progresso" `
    -m "- cli.py: entry point CLI" `
    -m "- requirements.txt, pyproject.toml, .env.example, .gitignore"

Write-Host ""
Write-Host "==> Configurando remote para $REPO_URL..." -ForegroundColor Cyan
git remote add origin $REPO_URL

Write-Host ""
Write-Host "==> Fazendo push para GitHub..." -ForegroundColor Cyan
Write-Host "    (Pode pedir login do GitHub na primeira vez.)" -ForegroundColor Yellow
git push -u origin main

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "OK. Repositorio sincronizado:" -ForegroundColor Green
Write-Host "  https://github.com/miguelribeirocodes/smart-pdf-translator" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Em outra maquina:" -ForegroundColor Cyan
Write-Host "  git clone $REPO_URL"
Write-Host "  cd smart-pdf-translator"
Write-Host "  python -m venv .venv"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  pip install -r requirements.txt"
