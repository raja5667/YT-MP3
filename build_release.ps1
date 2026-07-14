# Build a full release: PyInstaller onedir + Inno Setup installer
# Usage: .\build_release.ps1

Write-Host "==> Cleaning old build folders..." -ForegroundColor Cyan
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "==> Running PyInstaller..." -ForegroundColor Cyan
pyinstaller YTMP3-Pro.spec
if ($LASTEXITCODE -ne 0) { Write-Host "PyInstaller failed." -ForegroundColor Red; exit 1 }

Write-Host "==> Compiling installer with Inno Setup..." -ForegroundColor Cyan
& "D:\Users\Inno Setup 6\ISCC.exe" YTMP3-Pro.iss
if ($LASTEXITCODE -ne 0) { Write-Host "ISCC failed." -ForegroundColor Red; exit 1 }

Write-Host "==> Done! Installer is in .\Output\" -ForegroundColor Green
