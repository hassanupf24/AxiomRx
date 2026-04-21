@echo off
echo ========================================================
echo AxiomRx Windows Standalone Builder
echo ========================================================
echo.

echo 1. Installing standard dependencies...
pip install -r requirements.txt

echo 2. Installing PyInstaller packager...
pip install pyinstaller

echo 3. Compiling binary...
pyinstaller --noconfirm --onedir --windowed --name "AxiomRx_Pharmacy_System" main.py

echo.
echo ========================================================
echo BUILD COMPLETE! 
echo ========================================================
echo Your ready-to-run Windows directory is successfully generated.
echo To run the software without Python, go to: 
echo \dist\AxiomRx_Pharmacy_System\AxiomRx_Pharmacy_System.exe
echo.
echo NOTE: Ensure 'Tesseract-OCR' is installed on your Windows machine 
echo for the AI Prescription Reading to function effectively.
echo ========================================================
pause
