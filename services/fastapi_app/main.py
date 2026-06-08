"""
Task 12: FastAPI backend for the supply chain intelligence system.
Connects directly to PostgreSQL/SQLite, with optional Redis caching.
"""
import os
import sys
import uuid
import time
import json
import asyncio
import random
import base64
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Add directories to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "model_health"))
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db, SessionLocal, IS_SQLITE
from models import SupplierNode, RiskSignal, DisruptionEvent, SupplierSKULink
from fusion_service import fusion_service
from rerouting_service import rerouting_service
from copilot import query_copilot
from simulator import scenario_simulator
from notifications import trigger_all_notifications
from id_utils import resolve_id

security = HTTPBearer(auto_error=False)

# ── Redis connection (optional) ────────────────────────────────────────────
redis_client = None
try:
    import redis.asyncio as aioredis
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_client = aioredis.Redis(
        host=redis_host,
        port=6379,
        db=0,
        decode_responses=True,
        socket_timeout=0.5,
        socket_connect_timeout=0.5
    )
except Exception:
    print("Redis not available. Running without caching.")

# In-memory job store fallback when Redis is down
_job_store: Dict[str, dict] = {}

# Active WebSockets
alert_connections: List[WebSocket] = []

JWT_SECRET = "admin123"

# ── Pydantic Models ─────────────────────────────────────────────────────────
class SupplierSummary(BaseModel):
    id: str
    name: str
    country: str
    tier: int
    risk_score: float
    trend: str
    last_updated: str

class RerouteRequest(BaseModel):
    urgency: str = "normal"

class JobStatus(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict] = None
    error: Optional[str] = None

class SimulateRequest(BaseModel):
    supplier_id: str
    risk_score: float = Field(ge=0.0, le=1.0)

class DisruptionEventSchema(BaseModel):
    id: str
    occurred_at: str
    event_type: str
    severity: float
    affected_supplier_ids: List[str]
    predicted: bool
    agent_action: Optional[str] = None
    resolved_at: Optional[str] = None

class MetricsResponse(BaseModel):
    suppliers_monitored: int
    alerts_triggered_today: int
    avg_response_time_ms: float
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    username: str
    password: str

class CopilotChatRequest(BaseModel):
    message: str

class ScenarioRequest(BaseModel):
    scenario_type: str
    target_id: str
    multiplier: Optional[float] = 1.0

# ── Helpers ─────────────────────────────────────────────────────────────────
def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "secret": JWT_SECRET[:8],
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    if credentials is None:
        return "anonymous"
    try:
        payload = json.loads(base64.b64decode(credentials.credentials))
        if payload.get("secret") != JWT_SECRET[:8]:
            raise HTTPException(status_code=401, detail="Invalid token")
        exp = datetime.fromisoformat(payload["exp"])
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Token expired")
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

redis_online = True

async def redis_get(key: str) -> Optional[str]:
    global redis_online
    if redis_client and redis_online:
        try:
            return await redis_client.get(key)
        except Exception:
            print("Redis connection failed. Disabling Redis caching.")
            redis_online = False
    return _job_store.get(key, {}).get("_raw")

async def redis_setex(key: str, ttl: int, value: str):
    global redis_online
    if redis_client and redis_online:
        try:
            await redis_client.setex(key, ttl, value)
            return
        except Exception:
            print("Redis connection failed. Disabling Redis caching.")
            redis_online = False
    _job_store[key] = {"_raw": value}

async def broadcast_alert(alert: Dict):
    disconnected = []
    for ws in alert_connections:
        try:
            await ws.send_json(alert)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        try:
            alert_connections.remove(ws)
        except ValueError:
            pass

async def check_and_alert(supplier_id: str, risk_score: float, supplier_name: str = "Unknown"):
    if risk_score > 0.6:
        alert = {
            "type": "risk_alert",
            "supplier_id": supplier_id,
            "risk_score": risk_score,
            "threshold": 0.6,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Supplier {supplier_name} risk score {risk_score:.4f} exceeds threshold 0.6",
        }
        await broadcast_alert(alert)
        trigger_all_notifications(supplier_name, risk_score)

async def simulate_live_events():
    while True:
        await asyncio.sleep(random.randint(20, 40))
        db = SessionLocal()
        try:
            suppliers = db.query(SupplierNode).all()
            if suppliers and alert_connections:
                supplier = random.choice(suppliers)
                supplier_id = str(supplier.id)
                new_risk = min(1.0, random.uniform(0.5, 0.95))
                db.add(RiskSignal(
                    supplier_id=supplier.id,
                    timestamp=datetime.now(timezone.utc),
                    signal_type="gnn_risk_score",
                    value=new_risk,
                    source="Live_Simulation"
                ))
                db.commit()
                await check_and_alert(supplier_id, new_risk, supplier.name)
        except Exception as e:
            print(f"Live event simulation error: {e}")
        finally:
            db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Supply Chain Intelligence API started")
    task = asyncio.create_task(simulate_live_events())
    yield
    task.cancel()
    print("Shutting down...")

app = FastAPI(
    title="Supply Chain Disruption Intelligence API",
    description="Real-time supply chain risk monitoring, ML-powered disruption prediction, and autonomous rerouting.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Endpoints ───────────────────────────────────────────────────────────────
@app.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    if req.username == "admin" and req.password == "admin123":
        token = create_token(req.username)
        return TokenResponse(access_token=token)
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/suppliers", response_model=List[SupplierSummary])
async def list_suppliers(
    country: Optional[str] = None,
    min_risk: float = 0.0,
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    query = db.query(SupplierNode)
    if country:
        query = query.filter(SupplierNode.country == country)
    suppliers = query.all()

    results = []
    for s in suppliers:
        supplier_id_str = str(s.id)
        cache_key = f"fusion:{supplier_id_str}"
        cached = await redis_get(cache_key)

        if cached:
            risk_data = json.loads(cached)
            risk_score = risk_data.get("overall_risk_score", 0.3)
        else:
            latest_signal = db.query(RiskSignal).filter(
                RiskSignal.supplier_id == s.id,
                RiskSignal.signal_type == "gnn_risk_score"
            ).order_by(RiskSignal.timestamp.desc()).first()
            risk_score = latest_signal.value if latest_signal else 0.25

        trend = "stable"
        if risk_score > 0.6:
            trend = "up"
        elif risk_score < 0.3:
            trend = "down"

        if risk_score >= min_risk:
            results.append(SupplierSummary(
                id=supplier_id_str,
                name=s.name,
                country=s.country,
                tier=s.tier,
                risk_score=risk_score,
                trend=trend,
                last_updated=datetime.now(timezone.utc).isoformat()
            ))

    results.sort(key=lambda x: x.risk_score, reverse=True)
    return results

@app.get("/api/suppliers/{supplier_id}/risk")
async def get_supplier_risk(
    supplier_id: str,
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    supplier = db.query(SupplierNode).filter(SupplierNode.id == resolve_id(supplier_id)).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    risk_data = await fusion_service.predict_and_explain(supplier_id)

    import re
    shap_reasons = []
    for reason in risk_data.get("top_3_reasons", []):
        try:
            match = re.search(r'(.*?)\s*\(([-+0-9.]+)\)', reason)
            if match:
                feature, val_str = match.groups()
                val = float(val_str)
                shap_reasons.append({
                    "feature": feature.strip(),
                    "value": abs(val),
                    "direction": "positive" if val > 0 else "negative"
                })
            else:
                shap_reasons.append({
                    "feature": reason,
                    "value": 0.1,
                    "direction": "positive"
                })
        except Exception:
            pass

    return {
        "supplier_id": supplier_id,
        "risk_score": risk_data.get("overall_risk_score", 0.5),
        "fusion_score": risk_data.get("overall_risk_score", 0.5),
        "confidence": risk_data.get("confidence", 0.85),
        "top_3_reasons": risk_data.get("top_3_reasons", []),
        "gnn_score": risk_data.get("meta_features", {}).get("gnn_risk_score", 0.0),
        "tft_score": risk_data.get("meta_features", {}).get("tft_3day_forecast", 0.0),
        "geo_score": risk_data.get("meta_features", {}).get("geo_risk_score", 0.0),
        "tft_forecast": [
            {"day": "Today", "low": 10, "mid": 20, "high": 30},
            {"day": "Tomorrow", "low": 15, "mid": 25, "high": 40},
            {"day": "Day 3", "low": 20, "mid": 30, "high": 50}
        ],
        "shap_reasons": shap_reasons
    }

async def _trigger_reroute_logic(
    supplier_id: str,
    urgency: str,
    background_tasks: BackgroundTasks,
    db: Session
):
    supplier = db.query(SupplierNode).filter(SupplierNode.id == resolve_id(supplier_id)).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    job_id = str(uuid.uuid4())
    job_data = {"job_id": job_id, "status": "pending", "result": None, "error": None}
    await redis_setex(f"reroute:{job_id}", 3600, json.dumps(job_data))

    async def _run_optimization():
        # Update status to processing once starting
        job_processing = {"job_id": job_id, "status": "processing", "result": None, "error": None}
        await redis_setex(f"reroute:{job_id}", 3600, json.dumps(job_processing))
        try:
            result = rerouting_service.optimize_reroute(supplier_id, urgency)
            job_update = {
                "job_id": job_id,
                "status": "completed" if not result.error_code else "failed",
                "result": result.dict() if not result.error_code else None,
                "error": result.error_code
            }
            await redis_setex(f"reroute:{job_id}", 3600, json.dumps(job_update))
            await broadcast_alert({
                "type": "reroute_complete",
                "supplier_id": supplier_id,
                "message": f"Reroute completed for {supplier.name} - {len(result.sku_assignments)} SKUs reassigned."
            })
        except Exception as e:
            job_update = {"job_id": job_id, "status": "failed", "result": None, "error": str(e)}
            await redis_setex(f"reroute:{job_id}", 3600, json.dumps(job_update))

    background_tasks.add_task(_run_optimization)
    return {
        "job_id": job_id,
        "status": "pending",
        "supplier_id": supplier_id,
        "estimated_seconds": 30
    }

@app.post("/api/suppliers/{supplier_id}/reroute")
async def trigger_reroute_post(
    supplier_id: str,
    req: dict,
    background_tasks: BackgroundTasks,
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    urgency = req.get("urgency", "normal")
    return await _trigger_reroute_logic(supplier_id, urgency, background_tasks, db)

@app.get("/api/suppliers/{supplier_id}/reroute")
async def trigger_reroute_get(
    supplier_id: str,
    urgency: str = "normal",
    background_tasks: BackgroundTasks = None,
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    if background_tasks is None:
        # Create background tasks context if it's somehow missing (not standard but safe fallback)
        background_tasks = BackgroundTasks()
    return await _trigger_reroute_logic(supplier_id, urgency, background_tasks, db)

@app.get("/api/jobs/{job_id}", response_model=JobStatus)
@app.get("/api/reroute/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str, user: str = Depends(verify_token)):
    cached = await redis_get(f"reroute:{job_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**json.loads(cached))

@app.post("/api/copilot/chat")
async def copilot_chat(
    req: CopilotChatRequest,
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    response_msg = query_copilot(req.message, db)
    return {"response": response_msg}

@app.post("/api/simulate/scenario")
async def simulate_scenario(
    req: ScenarioRequest,
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    if req.scenario_type == "supplier_failure":
        res = scenario_simulator.simulate_supplier_failure(req.target_id, db)
    elif req.scenario_type == "port_closure":
        res = scenario_simulator.simulate_port_closure(req.target_id, db)
    elif req.scenario_type == "demand_surge":
        res = scenario_simulator.simulate_demand_surge(req.multiplier, db)
    else:
        raise HTTPException(status_code=400, detail="Invalid scenario type")
    return res

@app.post("/api/model-health/drift-check")
async def trigger_drift_check(
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        from drift_detector import detect_drift
        from retrain_pipeline import retrain_model_if_drift

        signals = db.query(RiskSignal).filter(RiskSignal.signal_type == "gnn_risk_score").all()
        current_scores = [s.value for s in signals]
        baseline_scores = np.random.beta(2, 5, max(100, len(current_scores))).tolist()

        drift_res = detect_drift(current_scores, baseline_scores)
        retrained = retrain_model_if_drift(drift_res["psi_value"])
        drift_res["retraining_triggered"] = retrained

        return drift_res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent/run/{supplier_id}")
async def run_agent(
    supplier_id: str,
    background_tasks: BackgroundTasks,
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    supplier = db.query(SupplierNode).filter(SupplierNode.id == resolve_id(supplier_id)).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    try:
        from agent import AgentRunner
        result = AgentRunner.run_for_supplier(supplier_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/disruptions", response_model=List[DisruptionEventSchema])
async def list_disruptions(
    event_type: Optional[str] = None,
    min_severity: float = 0.0,
    limit: int = Query(default=50, le=200),
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    query = db.query(DisruptionEvent).filter(DisruptionEvent.severity >= min_severity)
    if event_type:
        query = query.filter(DisruptionEvent.event_type == event_type)

    events = query.order_by(DisruptionEvent.occurred_at.desc()).limit(limit).all()

    result = []
    for e in events:
        # Handle affected_supplier_ids which may be JSON string in SQLite
        aids = e.affected_supplier_ids
        if isinstance(aids, str):
            try:
                aids = json.loads(aids)
            except Exception:
                aids = [aids]
        result.append(DisruptionEventSchema(
            id=str(e.id),
            occurred_at=e.occurred_at.isoformat() if hasattr(e.occurred_at, 'isoformat') else str(e.occurred_at),
            event_type=e.event_type,
            severity=e.severity,
            affected_supplier_ids=[str(sid) for sid in (aids or [])],
            predicted=e.predicted,
            agent_action=e.agent_action,
            resolved_at=e.resolved_at.isoformat() if e.resolved_at and hasattr(e.resolved_at, 'isoformat') else str(e.resolved_at) if e.resolved_at else None
        ))
    return result

@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics(
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    suppliers = db.query(SupplierNode).all()
    supplier_count = len(suppliers)

    high = 0
    medium = 0
    low = 0

    for s in suppliers:
        latest_signal = db.query(RiskSignal).filter(
            RiskSignal.supplier_id == s.id,
            RiskSignal.signal_type == "gnn_risk_score"
        ).order_by(RiskSignal.timestamp.desc()).first()
        score = latest_signal.value if latest_signal else 0.25

        if score > 0.6:
            high += 1
        elif score > 0.3:
            medium += 1
        else:
            low += 1

    alerts_today = db.query(DisruptionEvent).filter(
        DisruptionEvent.occurred_at >= datetime.now(timezone.utc) - timedelta(days=1)
    ).count()

    return MetricsResponse(
        suppliers_monitored=supplier_count,
        alerts_triggered_today=alerts_today,
        avg_response_time_ms=45.2,
        high_risk_count=high,
        medium_risk_count=medium,
        low_risk_count=low,
    )

@app.post("/api/simulate")
async def simulate_risk(
    req: SimulateRequest,
    user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    supplier = db.query(SupplierNode).filter(SupplierNode.id == resolve_id(req.supplier_id)).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    db.add(RiskSignal(
        supplier_id=supplier.id,
        timestamp=datetime.now(timezone.utc),
        signal_type="gnn_risk_score",
        value=req.risk_score,
        source="Manual_Simulation"
    ))
    db.commit()

    if req.risk_score > 0.6:
        event = DisruptionEvent(
            id=str(uuid.uuid4()) if IS_SQLITE else uuid.uuid4(),
            occurred_at=datetime.now(timezone.utc),
            event_type="Manual Disruption Simulation",
            severity=req.risk_score,
            affected_supplier_ids=[str(supplier.id)],
            predicted=False,
        )
        db.add(event)
        db.commit()

    await check_and_alert(req.supplier_id, req.risk_score, supplier.name)

    return {
        "status": "ok",
        "supplier_id": req.supplier_id,
        "new_risk": req.risk_score,
    }

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await websocket.accept()
    alert_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if websocket in alert_connections:
            alert_connections.remove(websocket)

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
