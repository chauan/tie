@echo off
chcp 65001 >nul
title VMconsole
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0VMconsole.ps1" %*
if errorlevel 1 pause
