"""
COA_html_plane.py — Visualisation interactive (Dash) ou export HTML statique
des trajectoires de vols avion issus des mesures OpenRadiation.

Modes :
  python COA_html_plane.py                   → démarre le serveur Dash local
  python COA_html_plane.py --export out.html → exporte snapshot HTML statique
"""

import argparse
import functools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from config import CFG, get_logger
from utils import load_measurements

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Visualisation trajectoires vols OpenRadiation")
    p.add_argument("--csv",        default=str(CFG.csv_path))
    p.add_argument("--export",     metavar="FILE", help="Export HTML statique vers FILE")
    p.add_argument("--host",       default=CFG.dash_host)
    p.add_argument("--port",       default=CFG.dash_port,  type=int)
    p.add_argument("--debug",      action="store_true",    default=CFG.dash_debug)
    p.add_argument("--n-frames",   default=500,            type=int)
    p.add_argument("--max-planes", default=500,            type=int)
    return p.parse_args()


def load_data(csv_path: Path) -> pd.DataFrame:
    data = load_measurements(
        csv_path,
        qualification="plane",
        usecols=["latitude", "longitude", "altitude", "startTime", "flightNumber", "qualification"],
        dropna_subset=["latitude", "longitude", "startTime", "flightNumber"],
    )
    data["flightNumber"] = data["flightNumber"].astype("category")
    return data


def build_figure(data: pd.DataFrame, t: pd.Timestamp, max_planes: int = 500) -> go.Figure:
    # searchsorted O(log n) + groupby évite N filtrages séparés
    end_idx = int(data["startTime"].searchsorted(t, side="right"))
    subset  = data.iloc[:end_idx]
    fig     = go.Figure()
    flights = subset["flightNumber"].unique()[:max_planes]
    grouped = subset[subset["flightNumber"].isin(flights)].groupby(
        "flightNumber", observed=True, sort=False
    )
    for flight, traj in grouped:
        traj = traj.sort_values("startTime")
        if len(traj) > 1:
            fig.add_trace(go.Scattergeo(
                lon=traj["longitude"], lat=traj["latitude"],
                mode="lines", line=dict(width=1), name=str(flight), hoverinfo="none"
            ))
        last_point = traj.iloc[-1]
        fig.add_trace(go.Scattergeo(
            lon=[last_point["longitude"]], lat=[last_point["latitude"]],
            mode="markers", marker=dict(size=5, color="red"),
            showlegend=False, hoverinfo="text",
            hovertext=f"Vol: {flight}<br>Altitude: {last_point['altitude']} m"
        ))
    fig.update_geos(
        projection_type="orthographic",
        projection_rotation=dict(lon=0, lat=30),
        showland=True,  landcolor="rgb(220, 220, 220)",
        showocean=True, oceancolor="LightBlue",
        showcountries=False, showcoastlines=True, coastlinecolor="black",
        resolution=50,
    )
    fig.update_layout(
        height=650,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend_title_text="Numéro de vol"
    )
    return fig


def export_html(data: pd.DataFrame, out_path: Path, n_frames: int, max_planes: int) -> None:
    log.info("Export HTML statique → %s", out_path)
    timestamps    = data["startTime"].drop_duplicates().reset_index(drop=True)
    frame_indices = np.linspace(0, len(timestamps) - 1, n_frames, dtype=int)
    t_last        = timestamps.iloc[frame_indices[-1]]
    fig           = build_figure(data, t_last, max_planes)
    fig.write_html(str(out_path), include_plotlyjs="cdn")
    log.info("Export terminé : %s", out_path)


def build_app(data: pd.DataFrame, n_frames: int, max_planes: int) -> Dash:
    timestamps    = data["startTime"].drop_duplicates().reset_index(drop=True)
    frame_indices = np.linspace(0, len(timestamps) - 1, n_frames, dtype=int)
    frame_times   = timestamps.iloc[frame_indices].reset_index(drop=True)

    app       = Dash(__name__)
    app.title = "Trajectoires de vols d'avions"
    app.layout = html.Div([
        html.H2("Visualisation des trajectoires de vols d'avions", style={"textAlign": "center"}),
        dcc.Graph(id="globe", config={"displayModeBar": False}),
        html.Div([
            dcc.Slider(
                id="time-slider",
                min=0, max=len(frame_times) - 1, step=1, value=0,
                marks={
                    i: str(frame_times[i].strftime("%H:%M"))
                    for i in range(0, len(frame_times), max(1, len(frame_times) // 10))
                },
                tooltip={"placement": "bottom", "always_visible": True},
            )
        ], style={"margin": "30px"}),
        html.Div(id="time-display", style={"textAlign": "center", "fontSize": "18px"}),
    ])

    @functools.lru_cache(maxsize=512)
    def _cached_fig(frame_idx: int) -> go.Figure:
        """Mémoïse les figures déjà calculées pour accélérer la navigation dans le slider."""
        t = frame_times[frame_idx]
        return build_figure(data, t, max_planes)

    @app.callback(
        Output("globe", "figure"),
        Output("time-display", "children"),
        Input("time-slider", "value"),
    )
    def update_globe(frame_idx):
        t = frame_times[frame_idx]
        return _cached_fig(frame_idx), f"Heure : {t.strftime('%Y-%m-%d %H:%M:%S')}"

    return app


def main() -> int:
    args     = parse_args()
    csv_path = Path(args.csv)

    if not csv_path.exists():
        log.error("Fichier CSV introuvable : %s", csv_path)
        return 1

    data = load_data(csv_path)

    if args.export:
        export_html(data, Path(args.export), args.n_frames, args.max_planes)
        return 0

    app = build_app(data, args.n_frames, args.max_planes)
    log.info("Démarrage du serveur Dash sur http://%s:%d", args.host, args.port)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
