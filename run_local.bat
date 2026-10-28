@echo off
chcp 65001 > nul
echo ========================================================
echo    Py Hosting - Mahalliy Server Ishga Tushirilmoqda...
echo ========================================================
echo.
echo Brauzerda oching: http://127.0.0.1:8000/
echo Demo Akkaunt:
echo    Username: demo
echo    Parol:    demo12345
echo.
echo To'xtatish uchun: Ctrl + C
echo --------------------------------------------------------

.\.venv\Scripts\daphne.exe -b 127.0.0.1 -p 8000 pyhosting.asgi:application
pause
