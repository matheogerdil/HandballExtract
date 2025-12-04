@echo off
echo ==========================================
echo INSTALLATION DES DEPENDANCES DU ROBOT
echo ==========================================
echo.

REM 1. Mise a jour de PIP
echo [1/4] Mise a jour de pip...
python -m pip install --upgrade pip

REM 2. Installation des bibliotheques Python
echo.
echo [2/4] Installation de Flet, Pandas, Playwright, PDFPlumber...
pip install flet playwright pdfplumber pandas openpyxl

REM 3. Installation des navigateurs pour le robot
echo.
echo [3/4] Installation des navigateurs Playwright...
playwright install

echo.
echo ==========================================
echo INSTALLATION TERMINEE !
echo Vous pouvez fermer cette fenetre.
echo ==========================================
pause