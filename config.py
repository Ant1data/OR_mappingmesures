"""
config.py — Configuration centralisée, surchargeable via variables d'environnement.

Toutes les variables peuvent être définies :
  - dans un fichier .env (chargé manuellement ou via python-dotenv),
  - dans les secrets / variables GitHub Actions,
  - ou directement via os.environ avant d'importer ce module.

Usage dans un script :
    from config import CFG, get_logger
    log = get_logger(__name__)
    log.info("CSV path: %s", CFG.csv_path)
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Chargement optionnel d'un fichier .env (si python-dotenv est installé)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv optionnel


# ---------------------------------------------------------------------------
# Dataclass de configuration
# ---------------------------------------------------------------------------
@dataclass
class Config:
    # ── Valeurs simples (surchargées via variables d'environnement) ───────────
    csv_filename:     str   = field(default_factory=lambda: os.environ.get("CSV_FILENAME", "measurements_withoutEnclosedObject.csv"))
    video_duration_s: int   = field(default_factory=lambda: int(os.environ.get("VIDEO_DURATION_SECONDS", "30")))
    target_fps:       int   = field(default_factory=lambda: int(os.environ.get("TARGET_FPS", "1")))
    video_fps:        int   = field(default_factory=lambda: int(os.environ.get("VIDEO_FPS", "2")))
    img_width:        int   = field(default_factory=lambda: int(os.environ.get("IMG_WIDTH", "900")))
    img_height:       int   = field(default_factory=lambda: int(os.environ.get("IMG_HEIGHT", "600")))
    map_dpi:          int   = field(default_factory=lambda: int(os.environ.get("MAP_DPI", "200")))
    start_date:       str   = field(default_factory=lambda: os.environ.get("START_DATE", "2015-01-01"))
    max_altitude:     float = field(default_factory=lambda: float(os.environ.get("MAX_ALTITUDE", "4000")))
    max_value:        float = field(default_factory=lambda: float(os.environ.get("MAX_VALUE", "0.4")))
    log_level:        str   = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "WARNING"))
    dash_host:        str   = field(default_factory=lambda: os.environ.get("DASH_HOST", "127.0.0.1"))
    dash_port:        int   = field(default_factory=lambda: int(os.environ.get("DASH_PORT", "8050")))
    dash_debug:       bool  = field(default_factory=lambda: os.environ.get("DASH_DEBUG", "false").lower() == "true")

    # ── Chemins (calculés dans __post_init__ pour éviter les lambdas imbriquées) ─
    base_dir:   Path = field(init=False)
    data_dir:   Path = field(init=False)
    output_dir: Path = field(init=False)
    maps_dir:   Path = field(init=False)
    videos_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        _here           = Path(__file__).parent
        self.base_dir   = Path(os.environ.get("BASE_DIR",   str(_here)))
        self.data_dir   = Path(os.environ.get("DATA_DIR",   str(self.base_dir / "out")))
        self.output_dir = Path(os.environ.get("OUTPUT_DIR", str(self.base_dir)))
        self.maps_dir   = Path(os.environ.get("MAPS_DIR",   str(self.output_dir / "last_frame")))
        self.videos_dir = Path(os.environ.get("VIDEOS_DIR", str(self.output_dir / "videos")))

    # ── Propriétés dérivées ────────────────────────────────────────────────────
    @property
    def csv_path(self) -> Path:
        return self.data_dir / self.csv_filename

    @property
    def max_frames(self) -> int:
        return self.video_duration_s * self.target_fps


# Instance globale (importée par les scripts)
CFG = Config()


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------
_logging_configured = False

def get_logger(name: str) -> logging.Logger:
    """Retourne un logger formaté pour CI et console."""
    global _logging_configured
    if not _logging_configured:
        logging.basicConfig(
            level=getattr(logging, CFG.log_level.upper(), logging.INFO),
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        _logging_configured = True
    return logging.getLogger(name)
