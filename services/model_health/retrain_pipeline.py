import os
import sys
import numpy as np
import pandas as pd
import joblib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "fastapi_app"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml_inference"))

from database import SessionLocal
from models import SupplierNode, RiskSignal
from model_fusion import train_meta_learner, explain_risk

def retrain_model_if_drift(psi_val: float) -> bool:
    """Trigger retraining of the meta-learner model if drift is high."""
    if psi_val < 0.1:
        print(f"PSI value {psi_val:.4f} is normal. No retraining required.")
        return False
        
    print(f"PSI value {psi_val:.4f} exceeds threshold. Triggering meta-learner retraining...")
    try:
        model = train_meta_learner()
        print("Retraining completed successfully.")
        return True
    except Exception as e:
        print(f"Failed to retrain meta-learner: {e}")
        return False

if __name__ == "__main__":
    retrain_model_if_drift(0.3)
