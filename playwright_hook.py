# playwright_hook.py
# simple hook : copie l'exécutable du driver Playwright (utile si PyInstaller ne l'inclut pas)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
hiddenimports = collect_submodules('playwright')
datas = collect_data_files('playwright')
