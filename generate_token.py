"""
generate_token.py — Génère le token OAuth2 YouTube pour l'upload automatisé.

À exécuter UNE SEULE FOIS en local (ouvre un navigateur pour l'authentification).
Le fichier token.json généré doit ensuite être copié dans les secrets GitHub.

Prérequis :
    - Avoir téléchargé client_secret.json depuis Google Cloud Console
      (API YouTube Data v3, scopes : youtube.upload)
    - pip install google-auth-oauthlib

Usage :
    python generate_token.py
    python generate_token.py --client-secret /chemin/vers/client_secret.json

Ensuite, dans GitHub :
    Settings → Secrets and variables → Actions → New repository secret
    Nom  : YOUTUBE_TOKEN_JSON
    Valeur : (contenu entier de token.json)
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Erreur : installez google-auth-oauthlib  →  pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Chemins de recherche pour client_secret.json (par ordre de priorité)
_SEARCH_PATHS = [
    Path(__file__).parent / "client_secret.json",   # même dossier que le script
    Path(__file__).parent.parent / "client_secret.json",  # dossier parent
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Génère token.json pour l'upload YouTube")
    p.add_argument(
        "--client-secret",
        default=None,
        help="Chemin vers client_secret.json (auto-détecté si absent)",
    )
    p.add_argument(
        "--output",
        default=str(Path(__file__).parent / "token.json"),
        help="Chemin de sortie du token (défaut : ./token.json)",
    )
    return p.parse_args()


def find_client_secret(override: str | None) -> Path:
    if override:
        p = Path(override)
        if not p.exists():
            print(f"Erreur : {p} introuvable.")
            sys.exit(1)
        return p
    for candidate in _SEARCH_PATHS:
        if candidate.exists():
            return candidate
    print(
        "Erreur : client_secret.json introuvable.\n"
        "Téléchargez-le depuis Google Cloud Console → APIs & Services → Credentials\n"
        "et placez-le dans le dossier OR_mappingmesures/ ou passez --client-secret."
    )
    sys.exit(1)


def main() -> None:
    args = parse_args()
    client_secret = find_client_secret(args.client_secret)
    output_path   = Path(args.output)

    print(f"Client secret : {client_secret}")
    print("Ouverture du navigateur pour l'authentification Google…")

    flow  = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0)

    token_json = creds.to_json()
    output_path.write_text(token_json, encoding="utf-8")

    print(f"\nToken enregistré : {output_path}")
    print("\n── Prochaine étape : copier dans GitHub Secrets ─────────────────────")
    print("  Settings → Secrets and variables → Actions → New repository secret")
    print("  Nom   : YOUTUBE_TOKEN_JSON")
    print(f"  Valeur: (contenu du fichier {output_path.name})\n")
    print("Contenu à copier :")
    print("─" * 60)
    print(token_json)
    print("─" * 60)


if __name__ == "__main__":
    main()
