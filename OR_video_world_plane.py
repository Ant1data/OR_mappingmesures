"""
COA_video_world_plane.py — Génère une vidéo MP4 mondiale des trajectoires de vols avion.
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

import contextily as ctx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from moviepy.editor import ImageSequenceClip
from pyproj import Transformer

from config import CFG, get_logger
from utils import load_measurements

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Génère la vidéo mondiale des vols avion")
    p.add_argument("--csv",        default=str(CFG.csv_path))
    p.add_argument("--output-dir", default=str(CFG.videos_dir))
    p.add_argument("--fps",        default=CFG.video_fps,        type=int)
    p.add_argument("--duration",   default=CFG.video_duration_s, type=int)
    return p.parse_args()


def main() -> int:
    args       = parse_args()
    csv_path   = Path(args.csv)
    videos_dir = Path(args.output_dir)
    videos_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        log.error("Fichier CSV introuvable : %s", csv_path)
        return 1

    data = load_measurements(
        csv_path,
        qualification="plane",
        dropna_subset=["latitude", "longitude", "startTime", "flightNumber"],
    )
    log.info("%d enregistrements de vols chargés", len(data))

    FPS          = args.fps
    total_frames = FPS * args.duration
    timestamps   = data["startTime"].drop_duplicates().reset_index(drop=True)
    if len(timestamps) == 0:
        log.warning("Aucune donnée de vol 'plane'.")
        return 0

    frame_indices = np.linspace(0, len(timestamps) - 1, total_frames, dtype=int)
    frame_times   = timestamps.iloc[frame_indices].reset_index(drop=True)

    today_str  = time.strftime("%d%m%Y")
    video_name = videos_dir / f"COA_World_plane_{today_str}.mp4"
    frame_dir  = videos_dir.parent / "frames_plane"
    frame_dir.mkdir(parents=True, exist_ok=True)

    mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

    def downsample_traj(traj, max_points: int = 200):
        if len(traj) <= max_points:
            return traj
        idx = np.linspace(0, len(traj) - 1, max_points, dtype=int)
        return traj.iloc[idx]

    MAX_LAT = 85.05112878
    xmin, ymin = mercator.transform(-180, -MAX_LAT)
    xmax, ymax = mercator.transform(180,   MAX_LAT)

    # Vérification colonnes aéroport une seule fois avant la boucle
    has_origin = "airportOrigin"      in data.columns
    has_dest   = "airportDestination" in data.columns

    visited_airports: dict = {}

    # Pré-calcul des positions d'aéroports (une seule fois, évite de rescanner le subset à chaque frame)
    airport_locations: dict[str, tuple[float, float]] = {}
    if has_origin or has_dest:
        parts = []
        if has_origin:
            parts.append(
                data[["airportOrigin", "longitude", "latitude"]]
                .rename(columns={"airportOrigin": "airport"})
            )
        if has_dest:
            parts.append(
                data[["airportDestination", "longitude", "latitude"]]
                .rename(columns={"airportDestination": "airport"})
            )
        airports_df = pd.concat(parts).dropna(subset=["airport"])
        for apt, grp in airports_df.groupby("airport"):
            row = grp.iloc[0]
            airport_locations[str(apt)] = (float(row["longitude"]), float(row["latitude"]))
        log.info("%d positions d'aéroports pré-calculées", len(airport_locations))

    t0 = time.time()

    # Création unique de la figure (réutilisée via ax.cla())
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)

    log.info("Génération de %d frames …", total_frames)
    for i, t in enumerate(frame_times):
        # searchsorted O(log n)
        end_idx = int(data["startTime"].searchsorted(t, side="right"))
        subset  = data.iloc[:end_idx]

        ax.cla()

        for flight, traj in subset.groupby("flightNumber", observed=True, sort=False):
            traj_ds = downsample_traj(traj.sort_values("startTime"))
            if len(traj_ds) > 1:
                xs, ys = mercator.transform(traj_ds["longitude"].values, traj_ds["latitude"].values)
                ax.plot(xs, ys, color="orange", linewidth=0.8, alpha=0.9)

        # Enregistre les aéroports nouvellement visibles dans le subset courant (lookup O(1))
        if airport_locations:
            for col in [c for c in ("airportOrigin", "airportDestination") if c in subset.columns]:
                for apt in subset[col].dropna().unique():
                    if apt not in visited_airports and apt in airport_locations:
                        visited_airports[apt] = airport_locations[apt]

        if visited_airports:
            lons = np.array([lon for lon, _ in visited_airports.values()])
            lats = np.array([lat for _, lat in visited_airports.values()])
            xs_pt, ys_pt = mercator.transform(lons, lats)
            ax.scatter(xs_pt, ys_pt, s=6, color="red", alpha=0.9)

        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_xticks([])
        ax.set_yticks([])
        try:
            ctx.add_basemap(ax, crs="EPSG:3857", source=ctx.providers.CartoDB.Positron)
        except Exception:
            pass

        flights_count  = subset["flightNumber"].nunique()
        airports_count = len(visited_airports)
        ax.text(0.02, 0.98,
                f"Vols cumulés: {flights_count}\nAéroports visités: {airports_count}\nDate: {t.strftime('%d-%m-%Y')}",
                transform=ax.transAxes, fontsize=12,
                bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.3"))

        fig.savefig(str(frame_dir / f"frame_{i:04d}.png"), dpi=100, bbox_inches="tight")

        if (i + 1) % 10 == 0 or i == total_frames - 1:
            elapsed   = time.time() - t0
            remaining = elapsed / (i + 1) * (total_frames - i - 1)
            log.info("  %d/%d frames | ~%.0fs restantes", i + 1, total_frames, remaining)

    plt.close(fig)

    frame_files = [str(frame_dir / f"frame_{i:04d}.png") for i in range(total_frames)]
    clip = ImageSequenceClip(frame_files, fps=FPS)
    clip.write_videofile(str(video_name), codec="libx264", audio=False, verbose=False, logger=None)
    shutil.rmtree(frame_dir, ignore_errors=True)
    log.info("Vidéo générée : %s", video_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
