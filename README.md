# 🏐 Automate Kalisport - Importateur de Feuilles de Match

Ce projet est un outil d'automatisation développé pour le club de **Bons-en-Chablais**. Il permet d'extraire automatiquement les statistiques (scores, buts, arrêts, sanctions) depuis les feuilles de match officielles (PDF) et de les insérer directement sur le site du club (Kalisport).

## 🚀 Fonctionnalités

* **Interface Graphique (GUI) :** Une interface simple et moderne (basée sur Flet) pour sélectionner l'équipe, le match et le fichier PDF.
* **Extraction Intelligente (PDF) :**
    * Détection automatique des équipes (Domicile/Extérieur) basée sur l'analyse du contenu.
    * Récupération du score final via plusieurs sources (Tableau, Log du match, Somme des buts) avec une **priorité absolue au "Déroulé du match"** pour garantir l'exactitude.
    * Gestion des formats de noms complexes (noms collés, majuscules/minuscules mélangées).
* **Recherche de Joueurs Avancée :** Algorithme de correspondance par "Signature" pour relier les noms mal formatés du PDF (ex: `BRUNIERLUCAS`) aux joueurs de la base de données Kalisport (ex: `BRUNIER Lucas`).
* **Automatisation Web :** Remplissage automatique du formulaire de match sur Kalisport via un robot (Playwright), avec gestion intelligente des champs de scores (Mi-temps vs Final).

## 📂 Structure du Projet

* `main_flet.py` : Le point d'entrée de l'application (Interface utilisateur).
* `extractor.py` : Le moteur d'analyse du PDF (Extraction des données brutes).
* `kalisport_bot.py` : Le robot qui navigue sur le web et remplit les formulaires.
* `teams.json` : Fichier de configuration contenant la liste des équipes et les liens des matchs.
* `install_deps.bat` : Script d'installation automatique des dépendances.
* `lancer_app.bat` : Raccourci pour lancer l'application.

## 🛠️ Installation

### Prérequis
* Avoir **Python** installé sur votre ordinateur (cochez bien **"Add Python to PATH"** lors de l'installation).

### Installation automatique
1.  Téléchargez ou décompressez le dossier du projet (ex: `handflet`).
2.  Double-cliquez sur le fichier **`install_deps.bat`**.
3.  Attendez que la fenêtre noire se ferme. Cela va installer toutes les librairies nécessaires (`flet`, `playwright`, `pandas`, `pdfplumber`) et les navigateurs.

## 🎮 Utilisation

1.  Double-cliquez sur le fichier **`lancer_app.bat`** (ou lancez `flet run main_flet.py` via un terminal).
2.  L'application s'ouvre.
3.  **Configuration :**
    * Sélectionnez l'**Équipe** (ex: Séniors Filles).
    * Sélectionnez le **Match** correspondant.
    * Vérifiez vos identifiants Kalisport (pré-remplis par défaut).
4.  **Étape 1 :** Cliquez sur **"Choisir le PDF"** et sélectionnez votre feuille de match.
5.  **Étape 2 :** Cliquez sur **"Prévisualiser les données"**.
    * Le script analyse le PDF.
    * Vérifiez le tableau qui s'affiche : les scores et les stats joueurs sont-ils cohérents ?
6.  **Étape 3 :** Cliquez sur **"Envoyer sur Kalisport"**.
    * Une fenêtre de navigateur va s'ouvrir.
    * Le robot va se connecter et remplir les données sous vos yeux.
    * Attendez le message de confirmation dans l'application.

## ⚙️ Configuration des Matchs (teams.json)

Pour ajouter de nouveaux matchs ou changer de saison, vous devez modifier le fichier `teams.json`.

**Structure du fichier :**
```json
{
  "club": "NOM DU CLUB",
  "teams": [
    {
      "label": "Nom de l'équipe (ex: -18 Filles)",
      "key": "Identifiant unique",
      "matches": [
        {
          "label": "Date - Adversaire",
          "date": "2025-10-05",
          "home_away": "D", 
          "opponent": "Nom Adversaire",
          "edit_url": "LIEN_URL_KALISPORT_POUR_EDITER_CE_MATCH"
        }
      ]
    }
  ]
}
