@echo off
echo Lancement de l'application Handball...

REM Se deplacer dans le dossier du projet (adapte dynamiquement a l'utilisateur)
cd /d "%USERPROFILE%\handflet"

REM Lancer l'application
flet run main_flet.py

REM Si ca plante, on laisse la fenetre ouverte pour lire l'erreur
if %ERRORLEVEL% NEQ 0 pause