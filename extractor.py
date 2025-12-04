import re
import pdfplumber
import pandas as pd
import unicodedata

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DEFAULT_TARGET = "BONS"
CLUB_ID = "5174011" 

FORCE_COLUMNS_FALLBACK = {
    "numero": 0, "nom": 1, "buts": 5, "7m": 6, 
    "arrets": 8, "jaunes": 9, "2min": 10, "rouges": 11
}

def _norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKD", s)
    return "".join([c for c in s if not unicodedata.combining(c)]).upper().strip()

def _clean_string(s):
    if not s: return ""
    s = s.replace("--", "-").replace("—", "-")
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def _smart_parse_identity(raw_val):
    s = _clean_string(raw_val)
    if not s: return "", ""

    if "-" in s:
        parts = s.split("-")
        nom_usage = parts[-1].strip()
        reste = parts[0].strip()
        tokens = reste.split()
        mixed_tokens = [t for t in tokens if not t.isupper()]
        if mixed_tokens:
            prenom = " ".join(mixed_tokens).title()
            return nom_usage, prenom

    tokens = s.split()
    if not tokens: return "", ""
    upper_tokens = [t for t in tokens if t.isupper() and len(t) > 1]
    mixed_tokens = [t for t in tokens if not t.isupper()]

    if mixed_tokens and upper_tokens:
        nom = upper_tokens[-1]
        prenom = " ".join(mixed_tokens)
    elif not mixed_tokens and len(tokens) >= 2:
        prenom = tokens[-1].title()
        nom = " ".join(tokens[:-1])
    else:
        nom = s # On envoie tout au robot si format inconnu
        prenom = ""
    return nom, prenom

def _find_column_indices(header_row):
    mapping = {}
    cleaned_header = [str(c or "").strip().lower() for c in header_row]
    for idx, col in enumerate(cleaned_header):
        if "n°" in col or col == "n" or "capt" in col: 
            if "nom" not in col: mapping["numero"] = idx
        if "nom" in col: mapping["nom"] = idx
        elif "buts" in col: mapping["buts"] = idx
        elif "7m" in col: mapping["7m"] = idx
        elif "tirs" in col: mapping["tirs"] = idx
        elif "arrets" in col: mapping["arrets"] = idx
        elif "av." in col or "av" == col: mapping["jaunes"] = idx
        elif "2" in col: mapping["2min"] = idx
        elif "dis" in col: mapping["rouges"] = idx
    return mapping

def _extract_score_via_max_sum(text_content):
    """
    ARME FATALE : Cherche tous les couples de nombres dans le texte.
    Celui qui a la somme la plus élevée est forcément le score final.
    """
    # Regex : Cherche "XX - XX" ou "XX espace XX" ou "XX.XX"
    # On évite les deux-points (:) pour ne pas prendre l'heure
    matches = re.findall(r"(?<![:\d])(\d{1,2})[ \t-]{1,3}(\d{1,2})(?![:\d])", text_content)
    
    candidates = []
    for m in matches:
        try:
            s1, s2 = int(m[0]), int(m[1])
            # Filtre de cohérence Handball :
            # 1. Pas de score < 3 (trop petit pour une fin de match)
            # 2. Pas de score > 65 (trop grand, c'est surement un code postal ou autre)
            # 3. La somme doit être > 15 (un match finit rarement à 5-5)
            if 3 <= s1 <= 65 and 3 <= s2 <= 65 and (s1 + s2) > 10:
                candidates.append((s1, s2))
        except: continue
    
    if not candidates:
        return 0, 0
    
    # On trie par somme décroissante (le plus gros total en premier)
    # Ex: (29, 29) -> somme 58. (12, 11) -> somme 23.
    candidates.sort(key=lambda x: x[0] + x[1], reverse=True)
    
    # Le gagnant est le score le plus élevé trouvé dans le document
    best_score = candidates[0]
    return best_score[0], best_score[1]

def parse_pdf(pdf_path: str, target_substr: str = DEFAULT_TARGET):
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        page1 = pdf.pages[0]
        tables = page1.extract_tables()
        if not tables: raise RuntimeError("Aucun tableau trouvé.")
        T = tables[0]

    # --- 1. DÉTECTION ÉQUIPES ---
    headers_indices = []
    for i, row in enumerate(T):
        row_str = " ".join([str(c or "") for c in row]).lower()
        if ("n°" in row_str or "capt" in row_str) and "nom" in row_str:
            headers_indices.append(i)

    if len(headers_indices) < 2: raise RuntimeError("Impossible de trouver les 2 équipes.")
    idx_table_1, idx_table_2 = headers_indices[0], headers_indices[1]

    target_clean = _norm(target_substr)
    content_table_1 = " ".join([" ".join([str(c or "") for c in row]) for row in T[idx_table_1:idx_table_2]])
    content_table_2 = " ".join([" ".join([str(c or "") for c in row]) for row in T[idx_table_2:]])
    
    score_t1 = content_table_1.upper().count(target_clean)
    score_t2 = content_table_2.upper().count(target_clean)
    if CLUB_ID in content_table_1: score_t1 += 100
    if CLUB_ID in content_table_2: score_t2 += 100

    if score_t2 > score_t1:
        is_home_target = False
        target_header_idx = idx_table_2
    else:
        is_home_target = True
        target_header_idx = idx_table_1

    # --- 2. EXTRACTION SCORE (Stratégie "MAX SUM") ---
    # On commence par essayer de lire le tableau proprement (pour la mi-temps)
    score_home_ht, score_away_ht = 0, 0
    score_home_ft, score_away_ft = 0, 0
    
    # Lecture Tableau
    for table in tables:
        t_str = str(table).lower()
        if "rec" in t_str and "vis" in t_str and ("score" in t_str or "période" in t_str):
            for row in table:
                row_txt = "".join([str(c or "") for c in row]).lower()
                nums = []
                for cell in row:
                    if cell:
                        found = re.findall(r'\d+', str(cell))
                        for n in found:
                            if int(n) < 150: nums.append(int(n))
                if len(nums) >= 2:
                    if ("période" in row_txt or "1mt" in row_txt) and nums[0] > 1:
                        score_home_ht, score_away_ht = nums[0], nums[1]
                    if "fin" in row_txt or "final" in row_txt:
                        score_home_ft, score_away_ft = nums[-2], nums[-1]

    # ARME FATALE : Si le tableau donne un score pourri (0 ou <5), on cherche le Max Score dans le texte
    # On cherche le score "Global" dans le texte (Home_Log, Away_Log)
    # Attention : L'ordre (Home/Away) dans le texte dépend de l'ordre d'affichage (souvent Domicile - Extérieur)
    # On suppose que le PDF affiche toujours "Domicile - Extérieur" dans les logs.
    
    s1_max, s2_max = _extract_score_via_max_sum(full_text)
    
    # Si le tableau a échoué (0-0 ou score ridicule < 5), on prend le Max Sum
    if score_home_ft < 5 or score_away_ft < 5:
        # On affecte le Max Sum.
        # ATTENTION : Il faut savoir qui est Domicile (s1) et Extérieur (s2)
        # Dans 99% des cas, le score est affiché "Domicile - Visiteur"
        score_home_ft = s1_max
        score_away_ft = s2_max

    # --- 3. JOUEURS ---
    col_map = _find_column_indices(T[target_header_idx])
    if "buts" not in col_map: col_map = FORCE_COLUMNS_FALLBACK

    rows_data = []
    for i in range(target_header_idx + 1, len(T)):
        row = T[i]
        row_str = "".join([str(c or "") for c in row])
        if "Officiel" in row_str or "Kiné" in row_str: break
        if not row_str.strip(): continue
        if target_header_idx == idx_table_1 and i >= idx_table_2: break

        def get_val(key):
            idx = col_map.get(key)
            if idx is None or idx >= len(row): return None
            return row[idx]

        raw_num = str(get_val("numero") or "").strip()
        raw_num = "".join([c for c in raw_num if c.isdigit()])
        raw_name = str(get_val("nom") or "").strip()
        if not raw_num: continue

        nom, prenom = _smart_parse_identity(raw_name)
        def to_int(v):
            s = "".join([c for c in str(v) if c.isdigit()])
            return int(s) if s else 0

        rows_data.append({
            "numero": int(raw_num),
            "nom": nom,
            "prenom": prenom,
            "buts": to_int(get_val("buts")),
            "but_7m": to_int(get_val("7m")),
            "tirs": to_int(get_val("tirs")),
            "arrets": to_int(get_val("arrets")),
            "jaunes": 1 if (str(get_val("jaunes") or "").strip().upper() in ["X", "1"]) else 0,
            "deux_min": to_int(get_val("2min")),
            "rouges": 1 if (str(get_val("rouges") or "").strip()) else 0
        })

    df = pd.DataFrame(rows_data)

    # --- 4. VALIDATION ET SÉCURITÉ ---
    sum_goals = int(df["buts"].sum()) if not df.empty else 0
    
    # On corrige NOTRE score via la somme des buts (toujours fiable)
    if is_home_target:
        score_home_ft = sum_goals
    else:
        score_away_ft = sum_goals
        
    # Pour l'ADVERSAIRE : Si son score est toujours 0, on garde le s1_max/s2_max calculé plus haut
    # Normalement géré par l'étape "Arme Fatale"

    return {
        "home_raw": "DOMICILE" if is_home_target else "ADVERSAIRE",
        "away_raw": "ADVERSAIRE" if is_home_target else "EXTERIEUR",
        "score_home": score_home_ft,
        "score_away": score_away_ft,
        "score_home_ht": score_home_ht,
        "score_away_ht": score_away_ht,
        "is_home": is_home_target
    }, df