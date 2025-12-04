import re
import unicodedata
import time
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError, Error as PlaywrightError
import os
import sys

if getattr(sys, "frozen", False):  
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base_path, "ms-playwright")

def _clean_text_for_match(text):
    if not text: return ""
    s = unicodedata.normalize("NFKD", str(text)).encode('ASCII', 'ignore').decode('utf-8')
    return s.upper().replace("-", "").replace(" ", "").strip()

class KalisportBot:
    def __init__(self, headless: bool = True, frame_selector: Optional[str] = None):
        self.headless = headless
        self._frame_selector = frame_selector
        self.p = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.scope = None 

    def __enter__(self):
        self.p = sync_playwright().start()
        self.browser = self.p.chromium.launch(headless=self.headless)
        self.ctx = self.browser.new_context()
        self.page = self.ctx.new_page()
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.scope = self.page
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.ctx: self.ctx.close()
            if self.browser: self.browser.close()
            if self.p: self.p.stop()
        except: pass

    def _is_alive(self):
        try: return not self.page.is_closed()
        except: return False

    def login(self, login_url, username, password):
        print(f"> Login...")
        try:
            self.page.goto(login_url, wait_until="domcontentloaded", timeout=20000)
            self.page.fill("input[name='login']", username)
            self.page.fill("input[name='mdp']", password)
            self.page.locator("[name='cmdOk']").first.click()
            time.sleep(3)
        except Exception as e: print(f"! Err login: {e}")

    def open_match_edit(self, edit_url):
        print(f"> Edit Match...")
        try:
            self.page.goto(edit_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
            if self._frame_selector:
                self.scope = self.page.frame_locator(self._frame_selector)
            else:
                self.scope = self.page
        except: pass

    def fill_match_scores(self, p1_home, p1_away, p2_home, p2_away):
        if not self._is_alive(): return
        
        # Calcul score
        final_home = (p1_home or 0) + (p2_home or 0)
        final_away = (p1_away or 0) + (p2_away or 0)
        
        print(f"> Insertion Scores : MT({p1_home}-{p1_away}) / 2MT({p2_home}-{p2_away}) / Fin({final_home}-{final_away})")
        
        # MAPPING EXACT des input scores
        mapping = {
            #Les Scores Finaux
            "resume[score_locaux]": final_home,
            "resume[score_visiteurs]": final_away,

            #Les Mi-Temps
            "resume[p1-locaux]": p1_home,
            "resume[p1-visiteurs]": p1_away,
            "resume[p2-locaux]": p2_home,
            "resume[p2-visiteurs]": p2_away
        }
        
        for field, value in mapping.items():
            if value is None: continue
            try: 
                inp = self.scope.locator(f"input[name='{field}']").first
                if inp.is_visible(): 
                    #Mettre le input null avant tout
                    inp.fill(str(value), timeout=500)
            except: pass

    def _find_row_by_name(self, nom_pdf, prenom_pdf):
        if not self._is_alive(): return None
        try:
            pdf_full = _clean_text_for_match(nom_pdf) + _clean_text_for_match(prenom_pdf)
            rows = self.scope.locator("tr:has(input[name*='[numero_presence]'])")
            count = rows.count()
            
            for i in range(count):
                row = rows.nth(i)
                row_text = row.text_content() or ""
                site_words = row_text.split()
                for word in site_words:
                    word_clean = _clean_text_for_match(word)
                    if len(word_clean) < 3: continue 
                    if word_clean in pdf_full:
                        print(f"  > Match trouvé : {word}")
                        return row
            
            exact = self.scope.locator(f"tr:has-text('{nom_pdf}')")
            if exact.count() > 0: return exact.first
        except: pass
        return None

    def _fill_numero_presence_in_row(self, row, numero):
        try:
            num_input = row.locator("input[name^='statsindiv['][name$='[numero_presence]']").first
            num_input.click(force=True)
            num_input.fill(str(numero))
            num_input.press("Tab")
            name_attr = num_input.get_attribute("name") or ""
            m = re.search(r"statsindiv\[(\d+)\]\[", name_attr)
            return m.group(1) if m else None
        except: return None

    def _fill_fields_by_pid(self, pid, values):
        if not self._is_alive(): return
        mapping = {
            1: ("buts", int(values.get("buts", 0))),
            2: ("but_7m", int(values.get("but_7m", 0))),
            3: ("jaunes", 1 if int(values.get("jaunes", 0)) > 0 else 0),
            4: ("deux_min", int(values.get("deux_min", 0))),
            5: ("arrets", int(values.get("arrets", 0))),
            7: ("rouges", int(values.get("rouges", 0))),
        }
        for champ, (_, val) in mapping.items():
            if val == 0: continue
            css = f"input[name='statsindiv[{pid}][stats_champ{champ}_rencontre]']"
            try: self.scope.fill(css, str(val), timeout=500)
            except: pass

    def fill_stats_dynamic(self, rows):
        print(f"> Remplissage ({len(rows)} joueurs)...")
        for r in rows:
            if not self._is_alive(): break
            nom = r.get("nom", "")
            prenom = r.get("prenom", "")
            try: numero = int(r.get("numero", 0))
            except: continue
            if numero <= 0: continue
            
            row = self._find_row_by_name(nom, prenom)
            if row:
                pid = self._fill_numero_presence_in_row(row, numero)
                if pid:
                    self._fill_fields_by_pid(pid, r)
                    print(f"  + OK: #{numero}")
                else:
                    print(f"  - Err PID: {nom}")
            else:
                print(f"  - Introuvable: {nom}")
            time.sleep(0.1)

    def click_validate(self):
        if not self._is_alive(): return
        print("> Validation...")
        try:
            self.scope.locator("[name='cmd-resume']").first.click(force=True, timeout=3000)
            time.sleep(5)
        except:
            print("! Bouton valider non trouvé.")