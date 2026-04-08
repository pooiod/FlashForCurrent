@echo off
set NAME=FlashHelper
set SCRIPT=main.py
set ICON=icon.ico
set DLL=pepflashplayer.dll

pyinstaller --name %NAME% --icon %ICON% --noconsole --onefile --add-binary "%DLL%;." %SCRIPT%
pyinstaller %NAME%.spec

echo Finished compiling
