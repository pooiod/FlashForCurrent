@echo off
set NAME=FlashHelper Installer
set SCRIPT=installer.py
set ICON=icon.ico
set DLL=pepflashplayer.dll

pyinstaller --name %NAME% --icon %ICON% --noconsole --onefile %SCRIPT%
pyinstaller %NAME%.spec

echo Finished compiling
