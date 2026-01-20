@echo off
title Instalacion - Hermes
color 0B

echo.
echo ========================================
echo           HERMES - Instalacion
echo ========================================
echo.
REM Verificar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python NO esta instalado
    echo.
    echo ========================================
    echo   NECESITAS INSTALAR PYTHON PRIMERO
    echo ========================================
    echo.
    echo 1. Ve a: https://www.python.org/downloads/
    echo 2. Descarga Python 3.11 o superior
    echo 3. IMPORTANTE: Durante la instalacion,
    echo    marca la opcion "Add Python to PATH"
    echo 4. Despues de instalar Python, 
ejecuta
    echo    este archivo INSTALAR.bat nuevamente
    echo.
    echo ========================================
    pause
    exit /b 1
)

echo Python detectado correctamente!
python --version
echo.
echo ========================================
echo.
echo Este proceso instalara las dependencias
echo necesarias para que Hermes funcione.
echo.
echo Solo necesitas hacer esto UNA VEZ.
echo.
echo ========================================
echo.
echo Actualizando pip...
python -m pip install --upgrade pip

echo.
echo Instalando dependencias desde requirements.txt...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ERROR: No se pudieron instalar las dependencias.
    echo Asegurate de tener conexion a internet.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo      Instalacion completada!
echo ========================================
echo.
echo Todas las dependencias de requirements.txt
echo han sido instaladas correctamente.
echo.
echo Ya puedes usar Hermes.
echo.
echo Ejecuta EJECUTAR.bat para iniciar
echo.
echo ========================================
pause
