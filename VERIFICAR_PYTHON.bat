@echo off
title Verificacion de Python - Hermes
color 0E

echo.
echo ========================================
echo      VERIFICACION DE PYTHON
echo ========================================
echo.
echo Este script verifica si Python esta
echo instalado correctamente en tu sistema.
echo.
echo ========================================
echo.

REM Verificar Python
echo Buscando Python...
echo.

python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python esta instalado!
    echo.
    python --version
    echo.
) else (
    echo [X] Python NO esta instalado
    echo.
    echo SOLUCION:
    echo 1. Ve a https://www.python.org/downloads/
    echo 2. Descarga Python 3.11 o superior
    echo 3. Durante instalacion, marca "Add Python to PATH"
    echo 4. Reinicia la computadora
    echo.
    goto :end
)

REM Verificar pip
echo Verificando pip...
echo.

python -m pip --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] pip esta disponible!
    echo.
    python -m pip --version
    echo.
) else (
    echo [X] pip NO esta disponible
    echo.
    echo SOLUCION:
    echo Reinstala Python y asegurate de incluir pip
    echo.
    goto :end
)

REM Verificar openpyxl
echo Verificando openpyxl...
python -c "import openpyxl" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] openpyxl esta instalado
) else (
    echo [X] openpyxl NO esta instalado
    echo     Ejecuta INSTALAR.bat para instalarlo
)
echo.

REM Verificar Pillow
echo Verificando Pillow...
python -c "from PIL import Image" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Pillow esta instalado
) else (
    echo [X] Pillow NO esta instalado
    echo     Ejecuta INSTALAR.bat para instalarlo
)
echo.

echo ========================================
echo        VERIFICACION COMPLETADA
echo ========================================
echo.
echo Si todo muestra [OK], puedes ejecutar
echo EJECUTAR.bat para usar Hermes.
echo.
echo Si algo muestra [X], ejecuta INSTALAR.bat
echo.

:end
echo ========================================
pause

