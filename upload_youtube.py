"""
upload_youtube.py — Upload une vidéo OpenRadiation sur YouTube.

Usage :
    python upload_youtube.py --zone World
    python upload_youtube.py --zone Europe --video path/to/video.mp4
    python upload_youtube.py --zone France --privacy unlisted

Variables d'environnement :
    YOUTUBE_TOKEN_JSON : token OAuth2 YouTube sérialisé en JSON (OBLIGATOIRE)
    VIDEOS_DIR         : dossier contenant les vidéos (défaut : ./videos)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import CFG, get_logger

log = get_logger(__name__)

# ── Métadonnées par zone ──────────────────────────────────────────────────────
_ZONE_META = {
    "World": {
        "title_prefix": "OpenRadiation — World map",
        "description_extra": (
            "Animated world map of all OpenRadiation measurements, "
            "from the first measurement to today."
        ),
    },
    "Europe": {
        "title_prefix": "OpenRadiation — Europe map",
        "description_extra": (
            "Animated map of OpenRadiation measurements over Europe, "
            "from the first measurement to today."
        ),
    },
    "France": {
        "title_prefix": "OpenRadiation — France map",
        "description_extra": (
            "Animated map of OpenRadiation measurements over France, "
            "from the first measurement to today."
        ),
    },
}

_BASE_DESCRIPTION = """\
Animated visualization of ambient dose-rate measurements (µSv/h) collected by
citizen scientists worldwide via the OpenRadiation project.

Data source: OpenRadiation — https://www.openradiation.net
License: ODbL (Open Database License)

Each dot represents a ground-level measurement. Color scale: blue (0 µSv/h) → red (≥ 0.4 µSv/h).
"""

_TAGS = [
    "openradiation", "radiation", "dosimeter",
    "ambient dose", "radioactivity", "citizen science",
    "geiger counter", "map", "visualization",
]

_CATEGORY_ID = "28"   # Science & Technology


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upload une vidéo OpenRadiation sur YouTube")
    p.add_argument("--zone",    choices=["World", "Europe", "France"], required=True,
                   help="Zone géographique de la vidéo")
    p.add_argument("--video",   default=None,
                   help="Chemin vers le fichier MP4 (auto-détecté si absent)")
    p.add_argument("--privacy", choices=["public", "unlisted", "private"],
                   default=os.environ.get("YOUTUBE_PRIVACY", "public"))
    p.add_argument("--title-suffix", default=None,
                   help="Suffixe ajouté au titre (défaut : mois en cours)")
    return p.parse_args()


def _resolve_video(zone: str, videos_dir: Path) -> Path:
    """Cherche le fichier MP4 le plus récent pour la zone donnée."""
    pattern = f"*_{zone}_*.mp4"
    candidates = sorted(videos_dir.glob(pattern))
    if not candidates:
        raise FileNotFoundError(
            f"Aucune vidéo trouvée pour la zone '{zone}' dans {videos_dir} "
            f"(pattern : {pattern})"
        )
    return candidates[-1]   # le plus récent (ordre alphabétique = ordre chronologique)


def _build_youtube_client() -> object:
    raw = os.environ.get("YOUTUBE_TOKEN_JSON") or os.environ.get("YOUTUBE_TOKEN")
    if not raw:
        raise RuntimeError(
            "Variable d'environnement YOUTUBE_TOKEN_JSON manquante.\n"
            "Exécutez generate_token.py et copiez le contenu de token.json dans le secret."
        )
    try:
        token_info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("YOUTUBE_TOKEN_JSON : JSON invalide") from exc

    creds = Credentials.from_authorized_user_info(
        token_info,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds)


def main() -> int:
    args = parse_args()

    videos_dir = Path(os.environ.get("VIDEOS_DIR", str(CFG.videos_dir)))

    # ── Résolution du fichier vidéo ───────────────────────────────────────────
    if args.video:
        video_path = Path(args.video)
        if not video_path.is_absolute():
            video_path = videos_dir / video_path
    else:
        video_path = _resolve_video(args.zone, videos_dir)

    if not video_path.exists():
        log.error("Fichier vidéo introuvable : %s", video_path)
        return 1

    log.info("Vidéo sélectionnée : %s (%.1f MB)", video_path, video_path.stat().st_size / 1e6)

    # ── Titre et description ──────────────────────────────────────────────────
    suffix = args.title_suffix or datetime.utcnow().strftime("%B %Y")
    meta   = _ZONE_META[args.zone]
    title  = f"{meta['title_prefix']} — {suffix}"[:100]
    description = f"{meta['description_extra']}\n\n{_BASE_DESCRIPTION}"

    # ── Client YouTube OAuth2 ─────────────────────────────────────────────────
    youtube = _build_youtube_client()

    # ── Upload ────────────────────────────────────────────────────────────────
    log.info("Upload YouTube : %s (%s)…", title, args.privacy)
    print(f"Uploading: {video_path.name} → '{title}'")

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title":       title,
                "description": description,
                "tags":        _TAGS,
                "categoryId":  _CATEGORY_ID,
            },
            "status": {
                "privacyStatus":          args.privacy,
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=MediaFileUpload(str(video_path), resumable=True),
    )

    response = request.execute()
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"Upload échoué : aucun video ID retourné. Réponse : {response}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Upload terminé : {url}")
    log.info("Upload terminé : %s", url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
