# main_flet.py
# -*- coding: utf-8 -*-
import os
import json
import tempfile
import traceback
import sys
import flet as ft
import pandas as pd

from extractor import parse_pdf
from kalisport_bot import KalisportBot

TEAMS_PATH = "teams.json"

# --- CONFIGURATION PLAYWRIGHT ---
def setup_playwright_path():
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base_path, "ms-playwright")
    else:
        pass

setup_playwright_path()

def load_teams():
    base = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "teams.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main(page: ft.Page):
    page.title = "Importer feuille de match → Kalisport"
    page.window_width = 1200
    page.window_height = 900
    page.scroll = "auto"

    current_match_info = {"data": None}
    current_df = {"data": None}

    try:
        teams_data = load_teams()
    except Exception as e:
        page.add(ft.Text(f"Erreur lecture teams.json : {e}", color="red"))
        return

    TEAMS = teams_data.get("teams", [])

    team_dropdown = ft.Dropdown(label="Équipe du club", width=400)
    match_dropdown = ft.Dropdown(label="Match", width=600)
    
    for t in TEAMS:
        team_dropdown.options.append(ft.dropdown.Option(t["label"]))
    if team_dropdown.options:
        team_dropdown.value = team_dropdown.options[0].text

    uploaded_file_name = ft.Text("Aucun fichier sélectionné", italic=True)
    uploaded_file_bytes = {"data": None}

    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    def pick_files_result(e: ft.FilePickerResultEvent):
        if e.files:
            f = e.files[0]
            uploaded_file_name.value = f.name
            with open(f.path, "rb") as pdf_file:
                uploaded_file_bytes["data"] = pdf_file.read()
            status_area.value = "Fichier chargé. Cliquez sur 'Prévisualiser'."
        page.update()

    file_picker.on_result = pick_files_result

    def on_team_change(e):
        sel = next((t for t in TEAMS if t["label"] == team_dropdown.value), None)
        match_dropdown.options.clear()
        if sel:
            for m in sel.get("matches", []):
                match_dropdown.options.append(ft.dropdown.Option(m["label"]))
            if match_dropdown.options:
                match_dropdown.value = match_dropdown.options[0].text
        page.update()

    team_dropdown.on_change = on_team_change
    on_team_change(None) 

    login_url_tf = ft.TextField(label="URL login", width=600, value=os.getenv("KALISPORT_LOGIN_URL", "https://handball-club-bons-en-chablais.com/connexion"))
    user_tf = ft.TextField(label="Email", width=300, value=os.getenv("KALISPORT_USER", ""))
    pass_tf = ft.TextField(label="Mot de passe", width=300, password=True, can_reveal_password=True, value=os.getenv("KALISPORT_PASSWORD", ""))

    status_area = ft.Text("", color="blue", weight="bold")
    warning_area = ft.Text("", color="orange", weight="bold")
    
    data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("N°")),
            ft.DataColumn(ft.Text("Nom")),
            ft.DataColumn(ft.Text("Prénom")),
            ft.DataColumn(ft.Text("Buts"), numeric=True),
            ft.DataColumn(ft.Text("7m"), numeric=True),
            ft.DataColumn(ft.Text("Arrêts"), numeric=True),
            ft.DataColumn(ft.Text("D.Min"), numeric=True),
            ft.DataColumn(ft.Text("Cartons")),
        ],
        rows=[]
    )
    
    table_container = ft.Container(content=data_table, visible=False, border=ft.border.all(1, "grey"), border_radius=10, padding=10)

    def run_extraction(e):
        if not uploaded_file_bytes["data"]:
            status_area.value = "❌ Veuillez charger un PDF d'abord."
            page.update()
            return

        status_area.value = "⏳ Analyse du PDF en cours..."
        warning_area.value = ""
        btn_publish.disabled = True
        table_container.visible = False
        page.update()

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file_bytes["data"])
                tmp_pdf_path = tmp.name

            # On utilise le target par défaut défini dans extractor.py ("BONS")
            match_info, df = parse_pdf(tmp_pdf_path) 
            os.remove(tmp_pdf_path)

            current_match_info["data"] = match_info
            current_df["data"] = df

            somme_buts = int(df["buts"].sum())
            score_equipe = match_info["score_home"] if match_info["is_home"] else match_info["score_away"]
            
            # Correction visuelle si le score est 0
            if score_equipe == 0 and somme_buts > 0:
                warning_area.value = f"⚠ Score Total non détecté (0). Utilisation de la somme des joueurs ({somme_buts})."
            elif score_equipe is not None and somme_buts != score_equipe:
                warning_area.value = f"⚠ ATTENTION : Somme des joueurs ({somme_buts}) ≠ Score équipe ({score_equipe})."
            else:
                warning_area.value = "✅ Cohérence score OK."

            data_table.rows.clear()
            for index, row in df.iterrows():
                cartons = []
                if row['jaunes']: cartons.append("🟨")
                if row['rouges']: cartons.append("🟥")
                
                data_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(row['numero']))),
                        ft.DataCell(ft.Text(row['nom'])),
                        ft.DataCell(ft.Text(row['prenom'])),
                        ft.DataCell(ft.Text(str(row['buts']))),
                        ft.DataCell(ft.Text(str(row['but_7m']))),
                        ft.DataCell(ft.Text(str(row['arrets']))),
                        ft.DataCell(ft.Text(str(row['deux_min']))),
                        ft.DataCell(ft.Text(" ".join(cartons))),
                    ])
                )

            mi = match_info
            msg = f"Match : {mi['home_raw']} ({mi['score_home']}) vs {mi['away_raw']} ({mi['score_away']}). Mi-temps : {mi['score_home_ht']}-{mi['score_away_ht']}"
            status_area.value = msg
            table_container.visible = True
            btn_publish.disabled = False 
            
        except Exception as err:
            status_area.value = f"❌ Erreur extraction : {err}"
            traceback.print_exc()
        
        page.update()

    def run_publication(e):
        sel_team = next((t for t in TEAMS if t["label"] == team_dropdown.value), None)
        sel_match = next((m for m in sel_team.get("matches", []) if m["label"] == match_dropdown.value), None)
        
        if not sel_match:
            status_area.value = "❌ Match cible introuvable."
            page.update()
            return

        status_area.value = "🚀 Lancement du Robot Kalisport..."
        page.update()

        def worker():
            try:
                setup_playwright_path()
                mi = current_match_info["data"]
                df = current_df["data"]

                # --- CALCUL SÉCURISÉ DES SCORES (Correction Négatif) ---
                total_home = mi.get("score_home") or 0
                ht_home = mi.get("score_home_ht") or 0
                
                total_away = mi.get("score_away") or 0
                ht_away = mi.get("score_away_ht") or 0

                # Calcul P2 = Total - P1. Si < 0, on met 0.
                p2_home = max(0, total_home - ht_home)
                p2_away = max(0, total_away - ht_away)

                with KalisportBot(headless=False) as bot:
                    bot.login(login_url_tf.value, user_tf.value, pass_tf.value)
                    bot.open_match_edit(sel_match.get("edit_url"))

                    # Remplissage Scores avec valeurs corrigées
                    bot.fill_match_scores(
                        p1_home=ht_home,
                        p1_away=ht_away,
                        p2_home=p2_home,
                        p2_away=p2_away,
                    )

                    bot.fill_stats_dynamic(df.to_dict(orient="records"))
                    bot.click_validate()
                
                status_area.value = "✅ PUBLICATION TERMINÉE AVEC SUCCÈS !"
            except Exception as err:
                status_area.value = f"❌ Erreur publication : {err}"
                traceback.print_exc()
            page.update()

        page.run_thread(worker)

    btn_file = ft.ElevatedButton("1. Choisir le PDF", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: file_picker.pick_files(allowed_extensions=["pdf"]))
    btn_extract = ft.ElevatedButton("2. Prévisualiser les données", icon=ft.Icons.PREVIEW, on_click=run_extraction)
    btn_publish = ft.ElevatedButton("3. Envoyer sur Kalisport", icon=ft.Icons.SEND, on_click=run_publication, disabled=True)

    page.add(
        ft.Column([
            ft.Text("🏐 Automate Feuille de Match", style="headlineMedium"),
            ft.Container(height=10),
            
            ft.Card(content=ft.Container(padding=10, content=ft.Column([
                ft.Text("Configuration", weight="bold"),
                ft.Row([team_dropdown, match_dropdown]),
                ft.Row([login_url_tf]),
                ft.Row([user_tf, pass_tf]),
            ]))),

            ft.Divider(),

            ft.Row([btn_file, uploaded_file_name]),
            ft.Row([btn_extract, btn_publish]),
            
            ft.Divider(),
            
            status_area,
            warning_area,
            
            ft.Text("Aperçu des données à envoyer :", style="titleMedium"),
            table_container
        ])
    )

if __name__ == "__main__":
    ft.app(target=main)