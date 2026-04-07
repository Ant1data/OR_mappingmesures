# OR Mapping Mesures

Outils Python pour télécharger, visualiser et exporter les mesures de débit de dose
de la base de données collaborative [OpenRadiation](https://www.openradiation.net/).

## Fonctionnalités

| Script | Description |
|---|---|
| `fetch_data.py` | Télécharge les mesures via l'API OpenRadiation et génère un CSV local |
| `OR_last_frame.py` | Génère une image PNG « dernier état » des mesures pour 3 zones (Monde, Europe, France) |
| `OR_video_groundlevel.py` | Génère des vidéos MP4 animées des mesures au sol |
| `OR_video_world_plane.py` | Génère une vidéo MP4 mondiale des trajectoires de vols en avion |
| `OR_html_plane.py` | Visualisation interactive Dash ou export HTML statique des vols avion |

## Prérequis

- Python ≥ 3.10
- `ffmpeg` disponible dans le PATH (requis pour la génération vidéo)
- Une clé API OpenRadiation (gratuite, à demander sur [openradiation.net](https://www.openradiation.net/))

## Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/<votre-utilisateur>/OR_mappingmesures.git
cd OR_mappingmesures

# 2. Créer et activer un environnement virtuel (recommandé)
python -m venv .venv
# Windows :
.venv\Scripts\activate
# Linux / macOS :
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt
```

## Configuration

Copiez le fichier `.env.example` en `.env` et renseignez au minimum votre clé API :

```bash
cp .env.example .env
# Puis éditez .env et renseignez OR_API_KEY
```

Toutes les variables sont documentées dans `.env.example`.  
Elles peuvent également être passées directement comme variables d'environnement
(utile pour GitHub Actions ou CI/CD).

## Utilisation

### 1. Télécharger les données

```bash
python fetch_data.py
# Avec options :
python fetch_data.py --start 2024-01-01 --end 2025-01-01 --qualification groundlevel
```

Le CSV est sauvegardé dans `out/` (dossier ignoré par git).

### 2. Générer les cartes statiques (PNG)

```bash
python OR_last_frame.py
```

Les images sont sauvegardées dans `last_frame/`.

### 3. Générer les vidéos sol (MP4)

```bash
python OR_video_groundlevel.py
```

### 4. Générer la vidéo mondiale des vols avion (MP4)

```bash
python OR_video_world_plane.py
```

Les vidéos sont sauvegardées dans `videos/`.

### 5. Visualisation interactive des vols avion

```bash
# Serveur Dash local (ouvrir http://127.0.0.1:8050)
python OR_html_plane.py

# Export HTML statique
python OR_html_plane.py --export output.html
```

## Structure du projet

```
OR_mappingmesures/
├── config.py                   # Configuration centralisée (variables d'env)
├── utils.py                    # Fonctions utilitaires partagées
├── fetch_data.py               # Téléchargement des données API
├── OR_last_frame.py            # Cartes PNG statiques
├── OR_video_groundlevel.py     # Vidéos mesures sol
├── OR_video_world_plane.py     # Vidéo vols avion mondiale
├── OR_html_plane.py            # Visualisation interactive Dash
├── requirements.txt            # Dépendances Python
├── .env.example                # Template des variables d'environnement
├── out/                        # Données CSV (ignoré par git)
├── last_frame/                 # Images PNG générées (ignoré par git)
└── videos/                     # Vidéos MP4 générées (ignoré par git)
```

## Variables d'environnement principales

| Variable | Défaut | Description |
|---|---|---|
| `OR_API_KEY` | — | **Obligatoire.** Clé API OpenRadiation |
| `DATA_DIR` | `./out` | Dossier contenant le CSV |
| `CSV_FILENAME` | `measurements_withoutEnclosedObject.csv` | Nom du fichier CSV |
| `MAX_ALTITUDE` | `4000` | Altitude maximale retenue (m) |
| `MAX_VALUE` | `0.4` | Débit de dose maximal retenu (µSv/h) |
| `LOG_LEVEL` | `WARNING` | Niveau de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

Voir `.env.example` pour la liste complète.

## Licence

À définir.
