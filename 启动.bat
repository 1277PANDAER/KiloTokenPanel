@echo off
chcp 65001 >nul
title KiloCode Token 面板服务
cd /d "%~dp0"
python server.py
pause
