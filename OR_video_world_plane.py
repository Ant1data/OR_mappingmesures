"""
OR_video_world_plane.py — Génère une vidéo MP4 mondiale des trajectoires de vols avion.
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import contextily as ctx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from moviepy.editor import ImageSequenceClip
from pyproj import Transformer

from config import CFG, get_logger
from utils import load_measurements

log = get_logger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────
MERCATOR_MAX_LAT: float = 85.05112878
FRAME_FIGSIZE: tuple[float, float] = (12.8, 7.2)
FRAME_DPI: int = 100
TRAJ_MAX_POINTS: int = 200
LOG_EVERY_N_FRAMES: int = 10

# ── Palette sombre / neon ───────────────────────────────────────────────────────
BG_COLOR: str = "#080818"          # fond figure
TRAJ_CMAP: LinearSegmentedColormap = LinearSegmentedColormap.from_list(
    "flight_age",
    ["#0066ff", "#00ccff", "#ffaa00", "#ff4400"],  # ancien → récent
)
GLOW_LAYERS: list[tuple[float, float]] = [
    # (linewidth, alpha)  — du halo extérieur au trait central
    (5.0, 0.04),
    (3.0, 0.10),
    (1.5, 0.30),
    (0.6, 0.90),
]
AIRPORT_GLOW_LAYERS: list[tuple[float, float]] = [
    (120, 0.05),  # (marker_size, alpha)
    (40,  0.15),
    (10,  0.70),
]
AIRPORT_CORE_COLOR: str  = "#ff6060"
AIRPORT_GLOW_COLOR: str  = "#ff2020"
HUD_BG_COLOR: str        = "#08081acc"   # RGBA hex (nécessite matplotlib ≥ 3.8)
HUD_EDGE_COLOR: str      = "#00d4ff"
HUD_TEXT_COLOR: str      = "#e8f4f8"

AirportMap = dict[str, tuple[float, float]]


# ── Structures de données ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class WorldBounds:
    xmin: float
    xmax: float
    ymin: float
    ymax: float


# ── Fonctions utilitaires ──────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Génère la vidéo mondiale des vols avion")
    p.add_argument("--csv",        default=str(CFG.csv_path))
    p.add_argument("--output-dir", default=str(CFG.videos_dir))
    p.add_argument("--fps",        default=CFG.video_fps,        type=int)
    p.add_argument("--duration",   default=CFG.video_duration_s, type=int)
    return p.parse_args()


def downsample_traj(traj: pd.DataFrame, max_points: int = TRAJ_MAX_POINTS) -> pd.DataFrame:
    """Réduit la trajectoire à `max_points` points équidistants."""
    if len(traj) <= max_points:
        return traj
    idx = np.linspace(0, len(traj) - 1, max_points, dtype=int)
    return traj.iloc[idx]


def build_world_bounds(mercator: Transformer) -> WorldBounds:
    xmin, ymin = mercator.transform(-180.0, -MERCATOR_MAX_LAT)
    xmax, ymax = mercator.transform(180.0,   MERCATOR_MAX_LAT)
    return WorldBounds(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)


def build_airport_locations(data: pd.DataFrame) -> AirportMap:
    """Retourne un dict {code_aéroport: (lon, lat)} depuis le DataFrame."""
    parts: list[pd.DataFrame] = []
    for col in ("airportOrigin", "airportDestination"):
        if col in data.columns:
            parts.append(
                data[[col, "longitude", "latitude"]].rename(columns={col: "airport"})
            )
    if not parts:
        return {}

    airports_df = pd.concat(parts).dropna(subset=["airport"])
    locations: AirportMap = {}
    for apt, grp in airports_df.groupby("airport"):
        row = grp.iloc[0]
        locations[str(apt)] = (float(row["longitude"]), float(row["latitude"]))

    log.info("%d positions d'aéroports pré-calculées", len(locations))
    return locations


def update_visited_airports(
    subset: pd.DataFrame,
    airport_locations: AirportMap,
    visited: AirportMap,
) -> None:
    """Ajoute dans `visited` les aéroports nouvellement visibles."""
    for col in ("airportOrigin", "airportDestination"):
        if col not in subset.columns:
            continue
        for apt in subset[col].dropna().unique():
            if apt not in visited and apt in airport_locations:
                visited[apt] = airport_locations[apt]


def _flight_color(age_ratio: float) -> tuple:
    """Retourne une couleur RGBA depuis TRAJ_CMAP selon l'âge normalisé [0=ancien, 1=récent]."""
    return TRAJ_CMAP(age_ratio)


def render_frame(
    *,
    ax: Axes,
    fig: Figure,
    subset: pd.DataFrame,
    visited_airports: AirportMap,
    mercator: Transformer,
    bounds: WorldBounds,
    timestamp: pd.Timestamp,
    out_path: Path,
) -> None:
    """Dessine et sauvegarde une frame en style sombre / neon."""
    ax.cla()
    ax.set_facecolor(BG_COLOR)

    # ── Fond carte sombre ──────────────────────────────────────────────────────
    ax.set_xlim(bounds.xmin, bounds.xmax)
    ax.set_ylim(bounds.ymin, bounds.ymax)
    ax.set_xticks([])
    ax.set_yticks([])
    with contextlib.suppress(Exception):
        ctx.add_basemap(ax, crs="EPSG:3857", source=ctx.providers.CartoDB.DarkMatter)

    # ── Dégradé temporel des vols ──────────────────────────────────────────────
    # Chaque vol est coloré selon l'âge de sa dernière mesure par rapport au timestamp courant
    t_min = subset["startTime"].min() if not subset.empty else timestamp
    t_range = max((timestamp - t_min).total_seconds(), 1.0)

    for _flight, traj in subset.groupby("flightNumber", observed=True, sort=False):
        traj_ds = downsample_traj(traj.sort_values("startTime"))
        if len(traj_ds) < 2:
            continue

        xs, ys = mercator.transform(
            traj_ds["longitude"].values, traj_ds["latitude"].values
        )

        # Âge du vol : 0 = très ancien, 1 = le plus récent
        last_t   = traj_ds["startTime"].iloc[-1]
        age_ratio = min(1.0, (last_t - t_min).total_seconds() / t_range)
        color = _flight_color(age_ratio)

        # Effet glow : plusieurs passes du halo vers le trait central
        for lw, alpha in GLOW_LAYERS:
            ax.plot(xs, ys, color=color, linewidth=lw, alpha=alpha, solid_capstyle="round")

    # ── Aéroports avec halo lumineux ──────────────────────────────────────────
    if visited_airports:
        lons   = np.array([lon for lon, _ in visited_airports.values()])
        lats   = np.array([lat for _, lat in visited_airports.values()])
        xs_pt, ys_pt = mercator.transform(lons, lats)

        for s, alpha in AIRPORT_GLOW_LAYERS:
            ax.scatter(xs_pt, ys_pt, s=s, color=AIRPORT_GLOW_COLOR, alpha=alpha,
                       linewidths=0, zorder=4)
        # Point central blanc
        ax.scatter(xs_pt, ys_pt, s=4, color="white", alpha=1.0, linewidths=0, zorder=5)

    # ── Overlay HUD ────────────────────────────────────────────────────────────
    flights_count = subset["flightNumber"].nunique()
    hud_text = (
        f"  VOLS CUMULÉS   {flights_count:>6}  \n"
        f"  AÉROPORTS      {len(visited_airports):>6}  \n"
        f"  DATE           {timestamp.strftime('%d %b %Y').upper():>10}  "
    )
    ax.text(
        0.012, 0.978,
        hud_text,
        transform=ax.transAxes,
        fontsize=11,
        va="top",
        ha="left",
        color=HUD_TEXT_COLOR,
        fontfamily="monospace",
        bbox=dict(
            facecolor="#0a0a22",
            edgecolor=HUD_EDGE_COLOR,
            linewidth=1.2,
            boxstyle="round,pad=0.5",
            alpha=0.82,
        ),
    )

    fig.savefig(out_path, dpi=FRAME_DPI, bbox_inches="tight", facecolor=BG_COLOR)


# ── Fonction principale ────────────────────────────────────────────────────────
def main() -> int:
    args = parse_args()
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

    fps          = args.fps
    total_frames = fps * args.duration
    timestamps   = data["startTime"].drop_duplicates().reset_index(drop=True)

    if timestamps.empty:
        log.warning("Aucune donnée de vol 'plane'.")
        return 0

    frame_indices = np.linspace(0, len(timestamps) - 1, total_frames, dtype=int)
    frame_times   = timestamps.iloc[frame_indices].reset_index(drop=True)

    today_str  = datetime.today().strftime("%d%m%Y")
    video_name = videos_dir / f"COA_World_plane_{today_str}.mp4"
    frame_dir  = videos_dir.parent / "frames_plane"
    frame_dir.mkdir(parents=True, exist_ok=True)

    mercator          = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    bounds            = build_world_bounds(mercator)
    airport_locations = build_airport_locations(data)
    visited_airports: AirportMap = {}

    fig, ax = plt.subplots(figsize=FRAME_FIGSIZE, dpi=FRAME_DPI)
    fig.patch.set_facecolor(BG_COLOR)
    t0 = time.perf_counter()
    log.info("Génération de %d frames …", total_frames)

    for i, t in enumerate(frame_times):
        end_idx = int(data["startTime"].searchsorted(t, side="right"))
        subset  = data.iloc[:end_idx]

        if airport_locations:
            update_visited_airports(subset, airport_locations, visited_airports)

        render_frame(
            ax=ax,
            fig=fig,
            subset=subset,
            visited_airports=visited_airports,
            mercator=mercator,
            bounds=bounds,
            timestamp=t,
            out_path=frame_dir / f"frame_{i:04d}.png",
        )

        if (i + 1) % LOG_EVERY_N_FRAMES == 0 or i == total_frames - 1:
            elapsed   = time.perf_counter() - t0
            remaining = elapsed / (i + 1) * (total_frames - i - 1)
            log.info("  %d/%d frames | ~%.0fs restantes", i + 1, total_frames, remaining)

    plt.close(fig)

    frame_files = [str(frame_dir / f"frame_{i:04d}.png") for i in range(total_frames)]
    clip = ImageSequenceClip(frame_files, fps=fps)
    clip.write_videofile(str(video_name), codec="libx264", audio=False, verbose=False, logger=None)
    shutil.rmtree(frame_dir, ignore_errors=True)
    log.info("Vidéo générée : %s", video_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
