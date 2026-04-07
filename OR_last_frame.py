"""
OR_last_frame.py — Génère une image PNG "dernier état" des mesures OpenRadiation
pour chaque zone géographique (World, Europe, France).

Variables d'environnement (ou arguments CLI) :
    MAPS_DIR     : dossier de sortie des PNG (défaut : ./last_frame)
    CSV_FILENAME : nom du fichier CSV (défaut : measurements_withoutEnclosedObject.csv)
    DATA_DIR     : dossier contenant le CSV (utilisé pour construire le chemin par défaut)
    MAX_ALTITUDE : altitude max en mètres (défaut : 4000)
    MAX_VALUE    : valeur max µSv/h (défaut : 0.4)
    MAP_DPI      : résolution des PNG (défaut : 200)
    LOG_LEVEL    : niveau de log (défaut : INFO)
"""

import argparse
import sys
from pathlib import Path 

import contextily as ctx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from pyproj import Transformer

from config import CFG, get_logger
from utils import load_measurements

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Génère les cartes last_frame OpenRadiation")
    p.add_argument("--output-dir",  default=str(CFG.maps_dir),    help="Dossier de sortie PNG")
    p.add_argument("--csv",         default=str(CFG.csv_path),    help="Chemin complet vers le CSV")
    p.add_argument("--max-altitude",default=CFG.max_altitude, type=float)
    p.add_argument("--max-value",   default=CFG.max_value,    type=float)
    p.add_argument("--dpi",         default=CFG.map_dpi,      type=int)
    p.add_argument("--zones",       nargs="+", default=["World", "Europe", "France"],
                   choices=["World", "Europe", "France"],
                   help="Zones à générer")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    csv_path   = Path(args.csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # 1) Transformeur géographique (WGS84 -> WebMercator)
    # --------------------------------------------------------
    mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

    # --------------------------------------------------------
    # 2) Chargement des données
    # --------------------------------------------------------
    if not csv_path.exists():
        log.error("Fichier CSV introuvable : %s", csv_path)
        return 1

    data = load_measurements(
        csv_path,
        qualification="groundlevel",
        max_altitude=args.max_altitude,
        max_value=args.max_value,
        dropna_subset=["latitude", "longitude", "startTime", "userId"],
    )

    # --------------------------------------------------------
    # 3) Zones géographiques
    # --------------------------------------------------------
    ALL_ZONES = {
        "World":  {"center": dict(lat=20, lon=0),    "lat_span": 90, "lon_span": 180},
        "Europe": {"center": dict(lat=50, lon=10),   "lat_span": 20, "lon_span": 25},
        "France": {"center": dict(lat=46.5, lon=2.5),"lat_span": 6,  "lon_span": 9},
    }
    zones = {k: v for k, v in ALL_ZONES.items() if k in args.zones}

    today_str = pd.Timestamp.now().strftime("%d%m%Y")

    # --------------------------------------------------------
    # 4) Colormap
    # --------------------------------------------------------
    cmap_photo1 = LinearSegmentedColormap.from_list(
        "blue_green_yellow_red",
        [(0.00, "blue"), (0.25, "green"), (0.50, "yellow"), (0.75, "orange"), (1.00, "red")]
    )

    # --------------------------------------------------------
    # 5) Helpers
    # --------------------------------------------------------
    MAX_LAT = 85.05112878

    def zone_bounds_to_merc(center, lat_span, lon_span):
        lat_min = max(center["lat"] - lat_span, -MAX_LAT)
        lat_max = min(center["lat"] + lat_span, MAX_LAT)
        lon_min = center["lon"] - lon_span
        lon_max = center["lon"] + lon_span
        xmin, ymin = mercator.transform(lon_min, lat_min)
        xmax, ymax = mercator.transform(lon_max, lat_max)
        return xmin, xmax, ymin, ymax

    def generate_map(zone_name, params):
        log.info("Génération carte : %s", zone_name)
        xmin, xmax, ymin, ymax = zone_bounds_to_merc(
            params["center"], params["lat_span"], params["lon_span"]
        )

        if zone_name == "Europe":
            x_center = (xmin + xmax) / 2
            y_center = (ymin + ymax) / 2
            half_size = max(xmax - xmin, ymax - ymin) / 2
            xmin, xmax = x_center - half_size, x_center + half_size
            ymin, ymax = y_center - half_size, y_center + half_size

        visible = data[
            (data["latitude"]  >= params["center"]["lat"] - params["lat_span"]) &
            (data["latitude"]  <= params["center"]["lat"] + params["lat_span"]) &
            (data["longitude"] >= params["center"]["lon"] - params["lon_span"]) &
            (data["longitude"] <= params["center"]["lon"] + params["lon_span"])
        ]

        if visible.empty:
            log.warning("Aucun point visible dans %s — carte ignorée", zone_name)
            return None

        xs, ys = mercator.transform(visible["longitude"].values, visible["latitude"].values)

        fig, ax = plt.subplots(
            figsize=(16, 16 if zone_name == "Europe" else 10),
            dpi=args.dpi
        )
        sc = ax.scatter(xs, ys, c=visible["value"], cmap=cmap_photo1,
                        s=4, vmin=0, vmax=args.max_value, linewidths=0, alpha=0.9)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_xticks([])
        ax.set_yticks([])

        try:
            ctx.add_basemap(ax, crs="EPSG:3857", source=ctx.providers.CartoDB.Voyager)
        except Exception as exc:
            log.warning("Fond de carte indisponible (%s) — carte générée sans tuiles", exc)

        ax.text(0.02, 0.98, f"{len(visible):,} mesures",
                transform=ax.transAxes, fontsize=12, va="top")
        ax.text(0.02, 0.95, f"{visible['userId'].nunique()} contributeurs",
                transform=ax.transAxes, fontsize=12, va="top")
        ax.text(0.02, 0.92, visible["startTime"].max().strftime("%d/%m/%Y"),
                transform=ax.transAxes, fontsize=12, va="top")

        cbar = plt.colorbar(sc, ax=ax, pad=0.01)
        cbar.set_label("Radiation µSv/h")

        out_path = output_dir / f"OR_{zone_name}_{today_str}.png"
        plt.savefig(out_path, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)
        log.info("PNG généré -> %s", out_path)
        return out_path

    # --------------------------------------------------------
    # 6) Boucle zones
    # --------------------------------------------------------
    generated = []
    for name, params in zones.items():
        result = generate_map(name, params)
        if result:
            generated.append(result)

    log.info("%d/%d cartes générées avec succès", len(generated), len(zones))
    return 0


if __name__ == "__main__":
    sys.exit(main())
