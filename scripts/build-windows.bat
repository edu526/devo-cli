@echo off
echo Building Devo CLI for Windows...
echo.

REM Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install dependencies
echo Installing dependencies...
pip install -q -r requirements.txt
pip install -q -e .

REM Install PyInstaller if not present
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build the binary
echo Building binary with PyInstaller...
pyinstaller devo.spec --clean

REM Check if build was successful
if exist dist\devo.exe (
    echo.
    echo Build successful!
    echo.
    echo Binary location: dist\devo.exe
    echo.
    echo Test the binary:
    echo   dist\devo.exe --version
    echo   dist\devo.exe --help
    echo.

    REM Test the binary
    echo Testing binary...
    dist\devo.exe --version

    echo.
    echo Binary is working!
) else (
    echo Build failed - binary not found
    exit /b 1
)
