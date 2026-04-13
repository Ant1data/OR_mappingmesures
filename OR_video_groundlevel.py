"""
COA_video_groundlevel.py — Génère des vidéos MP4 animées des mesures sol OpenRadiation.

Rendu des frames via matplotlib + contextily :
  - Tuiles cartographiques téléchargées UNE SEULE FOIS par zone (cache contextily).
  - Figure matplotlib réutilisée frame après frame (pas de recréation).
  - ~0.05–0.1 s/frame au lieu de ~1–2 s/frame avec Plotly/kaleido.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import contextily as cx
import matplotlib
matplotlib.use("Agg")                   # rendu hors-écran, pas de GUI
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import Transformer

from config import CFG, get_logger
from utils import load_measurements

log = get_logger(__name__)

# ── Constantes graphiques ────────────────────────────────────────────────────
_CMAP        = mcolors.LinearSegmentedColormap.from_list(
    "coa", ["blue", "green", "yellow", "red"]
)
_NORM        = mcolors.Normalize(vmin=0, vmax=0.4)
_TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)


def _merc(lon: np.ndarray, lat: np.ndarray):
    """Convertit lon/lat (EPSG:4326) → x/y Web Mercator (EPSG:3857)."""
    return _TRANSFORMER.transform(lon, lat)


def _zone_extent(center: dict, lat_range: float, lon_range: float) -> tuple:
    """Retourne (x_min, y_min, x_max, y_max) en Web Mercator."""
    x_min, y_min = _TRANSFORMER.transform(center["lon"] - lon_range, center["lat"] - lat_range)
    x_max, y_max = _TRANSFORMER.transform(center["lon"] + lon_range, center["lat"] + lat_range)
    return x_min, y_min, x_max, y_max


def _download_basemap(x_min: float, y_min: float, x_max: float, y_max: float) -> tuple:
    """Télécharge les tuiles CartoDB Voyager (mises en cache automatiquement par contextily)."""
    log.info("  Téléchargement des tuiles (cache contextily)…")
    img, ext = cx.bounds2img(
        x_min, y_min, x_max, y_max,
        ll=False,
        source=cx.providers.CartoDB.Voyager,
    )
    return img, ext


def _build_figure(basemap_img, basemap_ext, x_min, y_min, x_max, y_max, img_w, img_h):
    """
    Crée la figure matplotlib UNE fois par zone.
    Retourne (fig, scatter, ann_mesures, ann_contrib, ann_date).
    """
    # Marge droite pour la colorbar (0.85 → laisse 15 % de place)
    fig, ax = plt.subplots(figsize=(img_w / 100, img_h / 100), dpi=100)
    fig.subplots_adjust(left=0, right=0.85, top=1, bottom=0)

    ax.imshow(basemap_img, extent=basemap_ext, aspect="auto", interpolation="bilinear")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.axis("off")

    scatter = ax.scatter([], [], c=[], s=6, alpha=0.8, linewidths=0, cmap=_CMAP, norm=_NORM)

    sm = cm.ScalarMappable(cmap=_CMAP, norm=_NORM)
    sm.set_array([0, 0.4])
    cbar = fig.colorbar(
        sm, ax=ax,
        ticks=[0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4],
        fraction=0.046, pad=0.04,
        shrink=0.5, aspect=15,
    )
    cbar.set_label("Radiation µSv/h", fontsize=10)
    cbar.ax.yaxis.set_tick_params(labelsize=9)
    cbar.ax.set_yticklabels([f"{v:.2f}" for v in [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4]])

    kw = dict(
        transform=ax.transAxes, fontsize=11, va="top",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.75, lw=0),
    )
    ann_m = ax.text(0.01, 0.985, "0 mesures",       **kw)
    ann_c = ax.text(0.01, 0.930, "0 contributeurs", **kw)
    ann_d = ax.text(0.01, 0.875, "",                **kw)

    return fig, scatter, ann_m, ann_c, ann_d


def _frames_to_video_ffmpeg(frame_dir: Path, video_path: Path, fps: int) -> None:
    """Assemble les frames PNG en MP4 via ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i",         str(frame_dir / "frame_%04d.png"),
        "-c:v",       "libx264",
        "-pix_fmt",   "yuv420p",
        str(video_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg a échoué (code {result.returncode}) :\n"
            + result.stderr.decode(errors="replace")
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Génère les vidéos groundlevel OpenRadiation")
    p.add_argument("--csv",          default=str(CFG.csv_path))
    p.add_argument("--output-dir",   default=str(CFG.videos_dir))
    p.add_argument("--duration",     default=CFG.video_duration_s, type=int)
    p.add_argument("--fps",          default=CFG.target_fps,       type=int)
    p.add_argument("--start-date",   default=CFG.start_date)
    p.add_argument("--max-altitude", default=CFG.max_altitude,     type=float)
    p.add_argument("--max-value",    default=CFG.max_value,        type=float)
    p.add_argument("--img-width",    default=CFG.img_width,        type=int)
    p.add_argument("--img-height",   default=CFG.img_height,       type=int)
    p.add_argument("--zones",        nargs="+",
                   default=["World", "Europe", "France"],
                   choices=["World", "Europe", "France"])
    return p.parse_args()


def main() -> int:
    args = parse_args()

    csv_path   = Path(args.csv)
    videos_dir = Path(args.output_dir)
    videos_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Fichier CSV introuvable : {csv_path}\n"
            f"  DATA_DIR       = {os.environ.get('DATA_DIR', '(non défini)')}\n"
            f"  Répertoire courant = {Path.cwd()}\n"
            f"  Contenu du dossier parent : {list(csv_path.parent.iterdir()) if csv_path.parent.exists() else '(dossier absent)'}"
        )

    # ── Chargement des données ────────────────────────────────────────────────
    data = load_measurements(
        csv_path,
        qualification="groundlevel",
        max_altitude=args.max_altitude,
        max_value=args.max_value,
        usecols=["value", "startTime", "latitude", "longitude",
                 "qualification", "userId", "altitude"],
        dropna_subset=["latitude", "longitude", "startTime", "userId"],
    )
    data = data[data["startTime"] >= pd.Timestamp(args.start_date)]
    log.info("%d mesures après filtre de date", len(data))

    first_time = data["startTime"].min()
    last_time  = data["startTime"].max()
    if pd.isna(first_time) or pd.isna(last_time):
        log.error("Aucune donnée temporelle valide.")
        return 1

    MAX_FRAMES   = args.duration * args.fps
    frame_times  = pd.date_range(start=first_time, end=last_time, periods=MAX_FRAMES)
    total_frames = len(frame_times)
    today_str    = pd.Timestamp.now().strftime("%d%m%Y")
    IMG_W        = args.img_width
    IMG_H        = args.img_height

    ALL_ZOOMS = {
        "World":  {"center": dict(lat=0,    lon=0),   "lat_range": 80, "lon_range": 175},
        "Europe": {"center": dict(lat=50,   lon=10),  "lat_range": 15, "lon_range": 25},
        "France": {"center": dict(lat=46.5, lon=2.5), "lat_range": 6,  "lon_range": 9},
    }
    zooms = {k: v for k, v in ALL_ZOOMS.items() if k in args.zones}

    for zone_name, zone_params in zooms.items():
        video_path = videos_dir / f"COA_{zone_name}_{today_str}.mp4"
        frame_dir  = videos_dir.parent / f"frames_tmp_{zone_name}"
        frame_dir.mkdir(parents=True, exist_ok=True)

        center    = zone_params["center"]
        lat_range = zone_params["lat_range"]
        lon_range = zone_params["lon_range"]
        lat_min   = center["lat"] - lat_range
        lat_max   = center["lat"] + lat_range
        lon_min   = center["lon"] - lon_range
        lon_max   = center["lon"] + lon_range

        x_min, y_min, x_max, y_max = _zone_extent(center, lat_range, lon_range)

        # ── Pré-filtrage géographique ─────────────────────────────────────────
        zone_data = data[
            (data["latitude"]  >= lat_min) & (data["latitude"]  <= lat_max) &
            (data["longitude"] >= lon_min) & (data["longitude"] <= lon_max)
        ].copy()

        # Conversion Web Mercator (une seule fois pour toute la zone)
        x_merc, y_merc = _merc(
            zone_data["longitude"].values,
            zone_data["latitude"].values,
        )
        st_arr  = zone_data["startTime"].values.astype("datetime64[ns]")
        val_arr = zone_data["value"].values
        uid_arr = zone_data["userId"].values

        # ── Pré-calculs vectorisés ────────────────────────────────────────────
        frame_t_np = frame_times.values.astype("datetime64[ns]")
        cum_ends   = np.searchsorted(st_arr, frame_t_np, side="right")

        seen_users_counts = np.empty(total_frames, dtype=np.intp)
        seen:     set = set()
        prev_end: int = 0
        for i, end in enumerate(cum_ends):
            end = int(end)
            if end > prev_end:
                seen.update(uid_arr[prev_end:end].tolist())
                prev_end = end
            seen_users_counts[i] = len(seen)

        # ── Tuiles cartographiques (téléchargées une seule fois) ──────────────
        basemap_img, basemap_ext = _download_basemap(x_min, y_min, x_max, y_max)

        # ── Figure matplotlib (créée une seule fois par zone) ─────────────────
        fig, scatter, ann_m, ann_c, ann_d = _build_figure(
            basemap_img, basemap_ext, x_min, y_min, x_max, y_max, IMG_W, IMG_H
        )

        log.info("Rendu %s (%d frames)…", zone_name, total_frames)

        for i, t in enumerate(frame_times):
            end = int(cum_ends[i])

            # Mise à jour du scatter uniquement (pas de recréation de figure)
            if end > 0:
                scatter.set_offsets(np.column_stack([x_merc[:end], y_merc[:end]]))
                scatter.set_array(val_arr[:end])
            else:
                scatter.set_offsets(np.empty((0, 2)))
                scatter.set_array(np.array([]))

            ann_m.set_text(f"{end:,} mesures")
            ann_c.set_text(f"{int(seen_users_counts[i]):,} contributeurs")
            ann_d.set_text(t.strftime("%d/%m/%Y"))

            fig.savefig(str(frame_dir / f"frame_{i:04d}.png"), dpi=100)

            if (i + 1) % 10 == 0 or i == total_frames - 1:
                log.info("  %d/%d frames rendues [%s]", i + 1, total_frames, zone_name)

        plt.close(fig)

        # ── Assemblage MP4 ────────────────────────────────────────────────────
        _frames_to_video_ffmpeg(frame_dir, video_path, fps=args.fps)
        shutil.rmtree(frame_dir)
        log.info("Vidéo générée : %s", video_path)

    log.info("Toutes les vidéos groundlevel générées.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
