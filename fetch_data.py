"""
fetch_data.py — Télécharge les mesures OpenRadiation via l'API officielle
et les sauvegarde au format CSV attendu par les autres scripts.

Documentation API : https://www.openradiation.net/fr/api

Variables d'environnement :
    OR_API_KEY       : clé API OpenRadiation (OBLIGATOIRE en production)
    DATA_DIR         : dossier de sortie du CSV (défaut : ./out)
    CSV_FILENAME     : nom du fichier CSV (défaut : measurements_withoutEnclosedObject.csv)
    OR_START_DATE    : date de début ISO 8601 (défaut : 2015-01-01T00:00:00Z)
    OR_END_DATE      : date de fin ISO 8601 (défaut : maintenant)
    OR_PAGE_SIZE     : taille des pages API (défaut : 5000)
    OR_MAX_PAGES     : nombre max de pages à télécharger (défaut : 0 = tout)
    LOG_LEVEL        : niveau de log (défaut : INFO)

Usage CI (GitHub Actions) :
    python fetch_data.py
    python fetch_data.py --start 2024-01-01 --end 2025-01-01
"""

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from config import CFG, get_logger

log = get_logger(__name__)

OR_API_BASE = "https://api.openradiation.net/v2"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Télécharge les données OpenRadiation")
    p.add_argument("--api-key",   default=os.environ.get("OR_API_KEY", ""),
                   help="Clé API OpenRadiation (ou var OR_API_KEY)")
    p.add_argument("--output-dir", default=str(CFG.data_dir),
                   help="Dossier de sortie du CSV")
    p.add_argument("--filename",   default=CFG.csv_filename)
    p.add_argument("--start",      default=os.environ.get("OR_START_DATE", "2015-01-01T00:00:00Z"),
                   help="Date de début ISO 8601")
    p.add_argument("--end",        default=os.environ.get("OR_END_DATE", ""),
                   help="Date de fin ISO 8601 (défaut : maintenant)")
    p.add_argument("--page-size",  default=int(os.environ.get("OR_PAGE_SIZE", "5000")), type=int)
    p.add_argument("--max-pages",  default=int(os.environ.get("OR_MAX_PAGES", "0")), type=int,
                   help="Nb max de pages (0 = tout)")
    p.add_argument("--qualification", default="",
                   help="Filtrer par qualification : groundlevel, plane (vide = tout)")
    return p.parse_args()


def fetch_page(session: requests.Session, params: dict, page: int) -> dict:
    """Récupère une page de mesures depuis l'API OpenRadiation."""
    url = f"{OR_API_BASE}/measurements"
    page_params = {**params, "page": page}
    for attempt in range(1, 4):
        try:
            resp = session.get(url, params=page_params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            log.warning("Page %d, tentative %d/3 : %s", page, attempt, exc)
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Impossible de récupérer la page {page} après 3 tentatives")


def main() -> int:
    args = parse_args()

    if not args.api_key:
        log.error(
            "Clé API manquante. Définissez OR_API_KEY dans les secrets GitHub "
            "ou passez --api-key <clé>."
        )
        return 1

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / args.filename

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    base_params: dict = {
        "apiKey":    args.api_key,
        "pageSize":  args.page_size,
        "startTime": args.start,
    }
    if args.end:
        base_params["endTime"] = args.end
    if args.qualification:
        base_params["qualification"] = args.qualification

    all_records: list[dict] = []
    page = 1
    total_pages = None

    log.info("Début du téléchargement (start=%s, pageSize=%d)", args.start, args.page_size)

    while True:
        log.info("Page %d%s …", page, f"/{total_pages}" if total_pages else "")
        data = fetch_page(session, base_params, page)

        # Structure de réponse API OpenRadiation
        records = data.get("result", data.get("data", []))
        if not records:
            log.info("Aucun résultat sur la page %d — arrêt.", page)
            break

        all_records.extend(records)
        log.info("  %d enregistrements récupérés (total : %d)", len(records), len(all_records))

        # Pagination
        meta       = data.get("metadata", data.get("meta", {}))
        total_pages = meta.get("totalPages", meta.get("total_pages"))
        if total_pages and page >= total_pages:
            break
        if args.max_pages and page >= args.max_pages:
            log.info("Limite de %d pages atteinte.", args.max_pages)
            break
        if len(records) < args.page_size:
            break  # dernière page partielle

        page += 1
        time.sleep(0.2)  # politesse API

    if not all_records:
        log.error("Aucune donnée récupérée.")
        return 1

    df = pd.DataFrame(all_records)
    df.to_csv(out_path, sep=";", index=False)
    log.info("CSV sauvegardé : %s (%d lignes)", out_path, len(df))
    return 0


if __name__ == "__main__":
    sys.exit(main())
