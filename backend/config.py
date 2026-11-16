from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("SDN_DATA_DIR", PROJECT_ROOT / "data"))
DATABASE_PATH = Path(os.getenv("SDN_DATABASE", DATA_DIR / "sdn_dashboard.db"))
TELEMETRY_PATH = Path(os.getenv("SDN_TELEMETRY", DATA_DIR / "telemetry.csv"))
ALERTS_PATH = Path(os.getenv("SDN_ALERTS", DATA_DIR / "alerts.log"))
API_HOST = os.getenv("SDN_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("SDN_API_PORT", "8000"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("SDN_CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

