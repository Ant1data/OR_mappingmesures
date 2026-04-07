"""
utils.py — Fonctions utilitaires partagées entre les scripts OP_mappingmesures.

Usage :
    from utils import load_measurements
    df = load_measurements(csv_path, qualification="groundlevel", max_value=0.4)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from config import get_logger

log = get_logger(__name__)


def load_measurements(
    csv_path: Path,
    qualification: Optional[str] = None,
    max_altitude: Optional[float] = None,
    max_value: Optional[float] = None,
    usecols: Optional[List[str]] = None,
    dropna_subset: Optional[List[str]] = None,
    sort_by: str = "startTime",
) -> pd.DataFrame:
    """Charge, nettoie et filtre le CSV OpenRadiation.

    Parameters
    ----------
    csv_path : Path
        Chemin vers le fichier CSV (séparateur « ; »).
    qualification : str | None
        Filtre sur la colonne 'qualification' (ex : 'groundlevel', 'plane').
        None = aucun filtre.
    max_altitude : float | None
        Altitude maximum en mètres. None = pas de filtre.
    max_value : float | None
        Valeur maximum µSv/h. None = pas de filtre.
    usecols : list[str] | None
        Sous-ensemble de colonnes à charger. None = toutes les colonnes.
    dropna_subset : list[str] | None
        Colonnes dont NaN entraîne la suppression de la ligne.
    sort_by : str
        Colonne de tri (défaut : 'startTime'). Passer '' pour ne pas trier.

    Returns
    -------
    pd.DataFrame trié et filtré.
    """
    log.info("Chargement CSV : %s", csv_path)
    df = pd.read_csv(
        csv_path, sep=";", engine="python", on_bad_lines="skip",
        usecols=usecols,
    )

    # --- Conversions de type ---
    if "startTime" in df.columns:
        df["startTime"] = pd.to_datetime(df["startTime"], errors="coerce")
        if df["startTime"].dt.tz is not None:
            df["startTime"] = df["startTime"].dt.tz_convert(None)

    for col in ("value", "latitude", "longitude", "altitude"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- Filtres métier ---
    if qualification is not None:
        df = df[df["qualification"] == qualification]
    if max_altitude is not None and "altitude" in df.columns:
        df = df[df["altitude"] <= max_altitude]
    if max_value is not None and "value" in df.columns:
        df = df[df["value"] <= max_value]
    if dropna_subset:
        existing = [c for c in dropna_subset if c in df.columns]
        if existing:
            df = df.dropna(subset=existing)

    # --- Tri ---
    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by).reset_index(drop=True)

    log.info("%d mesures après filtrage", len(df))
    return df
