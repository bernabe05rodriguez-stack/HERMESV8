@echo off
title Generador de Ejecutable Hermes
color 0B

echo.
echo ==========================================
echo    GENERADOR DE EJECUTABLE PARA HERMES
echo ==========================================
echo.
echo 1. Instalando dependencias necesarias para compilar (PyInstaller)...
pip install pyinstaller Pillow
if %errorlevel% neq 0 (
    echo Error instalando PyInstaller. Verifica tu conexion a internet o tu instalacion de Python.
    pause
    exit /b
)

echo.
echo 2. Generando icono a partir de logo_left.png...
python -c "from PIL import Image; img = Image.open('logo_left.png'); img.save('icon.ico', format='ICO', sizes=[(256, 256)])"

echo.
echo 3. Creando el ejecutable (esto puede tardar unos minutos)...
echo.

rem --add-data format: source;destination
rem --collect-all ensures all dependencies of libraries are included
pyinstaller --noconsole --onefile ^
    --icon=icon.ico ^
    --name="Hermes" ^
    --add-data "scrcpy-win64-v3.2;scrcpy-win64-v3.2" ^
    --add-data "*.png;." ^
    --collect-all customtkinter ^
    --collect-all uiautomator2 ^
    --collect-all adbutils ^
    --hidden-import "PIL._tkinter_finder" ^
    Hermes.py

if %errorlevel% neq 0 (
    echo.
    echo !ERROR! Ha ocurrido un error durante la creacion del ejecutable.
    pause
    exit /b
)

echo.
echo ========================================================
echo.
echo    !EJECUTABLE CREADO CON EXITO!
echo.
echo    Lo encontraras en la carpeta: dist/Hermes.exe
echo    Puedes copiar ese archivo y enviarselo a tus amigos.
echo.
echo ========================================================
echo.
pause
