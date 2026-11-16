from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import ALERTS_PATH, CORS_ORIGINS, TELEMETRY_PATH
from .db import add_event, create_experiment, initialize_database, list_events, list_experiments
from .models import Event, Experiment, ExperimentRequest, Health
from .telemetry import read_latest, summarize
from .topology import TOPOLOGIES, get_topology


app = FastAPI(title="Self-Healing SDN API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/api/health", response_model=Health)
def health() -> Health:
    return Health(
        status="ok",
        database="available",
        telemetry_file="available" if TELEMETRY_PATH.exists() else "missing",
    )


@app.get("/api/topologies")
def topologies() -> dict[str, dict]:
    return TOPOLOGIES


@app.get("/api/topology/{name}")
def topology(name: str) -> dict:
    try:
        return get_topology(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown topology") from exc


@app.get("/api/telemetry")
def telemetry(limit: int = Query(default=100, ge=1, le=5000)) -> dict:
    rows = read_latest(TELEMETRY_PATH, limit)
    return {"rows": rows, "summary": summarize(rows)}


@app.get("/api/alerts")
def alerts(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, list[str]]:
    if not ALERTS_PATH.exists():
        return {"alerts": []}
    lines = ALERTS_PATH.read_text(encoding="utf-8").splitlines()
    return {"alerts": lines[-limit:]}


@app.get("/api/events", response_model=list[Event])
def events(limit: int = Query(default=100, ge=1, le=500)) -> list[dict]:
    return list_events(limit)


@app.post("/api/experiments", response_model=Experiment, status_code=201)
def plan_experiment(request: ExperimentRequest) -> dict:
    experiment_id = create_experiment(
        request.controller, request.topology, request.failure_link
    )
    add_event(
        "experiment_planned",
        "info",
        f"Experiment {experiment_id} planned",
        request.model_dump(),
    )
    return next(item for item in list_experiments() if item["id"] == experiment_id)


@app.get("/api/experiments", response_model=list[Experiment])
def experiments(limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    return list_experiments(limit)

