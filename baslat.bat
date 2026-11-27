@echo off
chcp 65001 >nul
title EX20v Ag Kontrol Merkezi - Yerel Ajan
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo [HATA] Python bulunamadi. https://www.python.org/downloads/ adresinden Python 3.11+ kurun
  echo        ve kurulumda "Add python.exe to PATH" kutusunu isaretleyin.
  pause
  exit /b 1
)

if not exist "agent\.venv\Scripts\python.exe" (
  echo Ilk calistirma: sanal ortam kuruluyor...
  %PY% -m venv "agent\.venv" || (echo [HATA] Sanal ortam kurulamadi & pause & exit /b 1)
)

echo Bagimliliklar kontrol ediliyor...
"agent\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r "agent\requirements.txt" || (echo [HATA] Paket kurulumu basarisiz & pause & exit /b 1)

start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:8080"
echo.
echo Windows Guvenlik Duvari sorarsa "Ozel aglar" icin izin verin (telefondan erisim icin).
echo Telefonda kullanmak icin: acilan sayfadaki QR kodu iPhone kamerasiyla okutun.
echo Kapatmak icin bu pencereyi kapatin.
"agent\.venv\Scripts\python.exe" "agent\server.py"
pause
