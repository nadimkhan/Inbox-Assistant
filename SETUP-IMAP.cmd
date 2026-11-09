@echo off
cd /d "%~dp0plugins\inbox-assistant"
python server\launch.py --setup
pause
