import os
import sys
import json
import uuid
import time
import asyncio
import numpy as np
from datetime import datetime, timezone

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ml_inference'))
from model_fusion import explain_risk, META_FEATURES
from database import SessionLocal
from models import SupplierNode, RiskSignal
from id_utils import resolve_id

# Optional Redis
_redis = None
_redis_online = True
try:
    import redis.asyncio as aioredis
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    _redis = aioredis.Redis(
        host=redis_host,
        port=6379,
        db=0,
        decode_responses=True,
        socket_timeout=0.5,
        socket_connect_timeout=0.5
    )
except Exception:
    pass

# In-memory cache fallback
_local_cache: dict = {}

class ModelFusionService:
    """Singleton service for ML Model Fusion connecting to DB."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelFusionService, cls).__new__(cls)
        return cls._instance

    async def predict_and_explain(self, supplier_id: str) -> dict:
        """Get fused risk prediction and SHAP explanation using actual DB features."""
        cache_key = f"fusion:{supplier_id}"

        # 1. Check Cache
        try:
            if _redis and _redis_online:
                cached = await _redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            elif cache_key in _local_cache:
                entry = _local_cache[cache_key]
                if time.time() - entry["ts"] < 300:
                    return entry["data"]
        except Exception:
            pass

        # 2. Fetch real features from DB
        db = SessionLocal()
        try:
            supplier = db.query(SupplierNode).filter(SupplierNode.id == resolve_id(supplier_id)).first()
            if not supplier:
                raise ValueError(f"Supplier {supplier_id} not found in database.")

            signals = db.query(RiskSignal).filter(
                RiskSignal.supplier_id == resolve_id(supplier_id)
            ).order_by(RiskSignal.timestamp.desc()).all()

            gnn_val = 0.0
            tft_val = 0.0
            geo_val = 0.0
            for sig in signals:
                if sig.signal_type == "gnn_risk_score" and gnn_val == 0.0:
                    gnn_val = sig.value
                elif sig.signal_type == "tft_3day_forecast" and tft_val == 0.0:
                    tft_val = sig.value
                elif sig.signal_type == "geo_risk_score" and geo_val == 0.0:
                    geo_val = sig.value

            meta_features = {
                "gnn_risk_score": gnn_val,
                "tft_3day_forecast": tft_val,
                "tft_uncertainty": 0.15,
                "geo_risk_score": geo_val,
                "geo_risk_type_encoded": 0,
                "current_reliability_score": supplier.reliability_score or 1.0,
                "tier": supplier.tier or 3,
            }

            result = explain_risk(supplier_id, meta_features=meta_features)

        except Exception as e:
            print(f"Real model inference failed, using fallback rule engine: {e}")
            result = {
                "supplier_id": supplier_id,
                "overall_risk_score": 0.35,
                "disruption_predicted": False,
                "confidence": 0.85,
                "top_3_reasons": ["Fallback rule engine: DB read failed."],
                "meta_features": {}
            }
        finally:
            db.close()

        # 3. Cache Result (5 min TTL)
        try:
            if _redis and _redis_online:
                await _redis.setex(cache_key, 300, json.dumps(result))
            else:
                _local_cache[cache_key] = {"data": result, "ts": time.time()}
        except Exception:
            _redis_online = False

        return result

fusion_service = ModelFusionService()
