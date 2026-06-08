"""
Task 09: Model fusion & SHAP explainability.

Combines outputs from GNN, TFT, and EfficientNet classifiers into a single
supplier risk score using an XGBoost meta-learner. Implements SHAP
explainability with human-readable explanations.
"""
import os
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from sklearn.model_selection import cross_val_score
from sklearn.metrics import f1_score, classification_report

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    from sklearn.ensemble import GradientBoostingClassifier
    HAS_XGB = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

try:
    import mlflow
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False

import joblib


# ── Feature Names for the Meta-Learner ──────────────────────────────────────
META_FEATURES = [
    "gnn_risk_score",
    "tft_3day_forecast",
    "tft_uncertainty",
    "geo_risk_score",
    "geo_risk_type_encoded",
    "current_reliability_score",
    "tier",
]


# ── Synthetic Meta-Learner Training Data ────────────────────────────────────
def generate_meta_dataset(n_samples: int = 5000) -> Tuple[pd.DataFrame, np.ndarray]:
    """Generate synthetic meta-learner training data by simulating
    outputs from the three sub-models."""
    np.random.seed(42)

    # Simulate sub-model outputs
    gnn_risk = np.random.beta(2, 5, n_samples)
    tft_forecast = np.random.beta(2, 5, n_samples)
    tft_uncertainty = np.random.uniform(0.05, 0.3, n_samples)
    geo_risk = np.random.choice([0.1, 0.5, 0.6, 0.7], n_samples, p=[0.4, 0.2, 0.2, 0.2])
    geo_type_encoded = np.random.randint(0, 4, n_samples)
    reliability = np.random.uniform(0.3, 1.0, n_samples)
    tier = np.random.choice([1, 2, 3], n_samples, p=[0.2, 0.3, 0.5])

    # Generate labels: disruption is more likely when sub-models agree on high risk
    risk_signal = 0.35 * gnn_risk + 0.3 * tft_forecast + 0.2 * geo_risk + 0.15 * (1 - reliability)
    noise = np.random.normal(0, 0.08, n_samples)
    prob = np.clip(risk_signal + noise, 0, 1)
    labels = (prob > 0.35).astype(int)

    # Enforce ~15% positive rate for reasonable class balance at meta level
    flip_indices = np.where(labels == 1)[0]
    if len(flip_indices) > int(0.15 * n_samples):
        excess = len(flip_indices) - int(0.15 * n_samples)
        to_flip = np.random.choice(flip_indices, excess, replace=False)
        labels[to_flip] = 0

    df = pd.DataFrame({
        "gnn_risk_score": gnn_risk,
        "tft_3day_forecast": tft_forecast,
        "tft_uncertainty": tft_uncertainty,
        "geo_risk_score": geo_risk,
        "geo_risk_type_encoded": geo_type_encoded,
        "current_reliability_score": reliability,
        "tier": tier,
    })

    return df, labels


# ── Meta-Learner Training ───────────────────────────────────────────────────
def train_meta_learner():
    """Train the XGBoost meta-learner with 5-fold cross-validation."""
    print("Generating meta-learner training data...")
    X, y = generate_meta_dataset(n_samples=5000)

    print(f"  Samples: {len(X)}, Positive rate: {y.mean():.2%}")

    if HAS_XGB:
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
        )
    else:
        print("  XGBoost not available, using sklearn GradientBoosting.")
        model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )

    # 5-fold cross-validation
    print("  Running 5-fold cross-validation...")
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="f1")
    print(f"  CV F1 scores: {[f'{s:.4f}' for s in cv_scores]}")
    print(f"  Mean CV F1:   {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # Train on full dataset
    model.fit(X, y)
    train_preds = model.predict(X)
    train_f1 = f1_score(y, train_preds)
    print(f"  Train F1:     {train_f1:.4f}")

    # Save model
    model_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "models"
    )
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "meta_learner.joblib")
    joblib.dump(model, model_path)
    print(f"  Model saved to {model_path}")

    if HAS_MLFLOW:
        mlflow.set_experiment("supply_chain_fusion")
        mlflow.start_run(run_name="xgboost_meta_learner")
        mlflow.log_params({
            "model": "XGBoost" if HAS_XGB else "GradientBoosting",
            "n_estimators": 200, "max_depth": 4, "lr": 0.1,
        })
        mlflow.log_metrics({
            "cv_f1_mean": cv_scores.mean(),
            "cv_f1_std": cv_scores.std(),
            "train_f1": train_f1,
        })
        mlflow.end_run()

    # ── SHAP Explainability ─────────────────────────────────────────────
    if HAS_SHAP:
        print("\n--- SHAP Analysis ---")
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)

        # Feature importance
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        importance = dict(zip(META_FEATURES, mean_abs_shap))
        sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        print("  Feature importance (mean |SHAP|):")
        for feat, val in sorted_importance:
            print(f"    {feat:35s} {val:.4f}")

        # Save SHAP values
        shap_path = os.path.join(model_dir, "shap_values.npy")
        np.save(shap_path, shap_values)
        print(f"  SHAP values saved to {shap_path}")
    else:
        print("\n  SHAP not installed. Skipping explainability.")
        # Fallback: use model feature importances
        if hasattr(model, "feature_importances_"):
            importance = dict(zip(META_FEATURES, model.feature_importances_))
            sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
            print("  Feature importance (model-native):")
            for feat, val in sorted_importance:
                print(f"    {feat:35s} {val:.4f}")

    return model


# ── GNN Attention Weights ───────────────────────────────────────────────────
def compute_gnn_attention_weights(supplier_id: str) -> Dict[str, float]:
    """Compute per-supplier attention weights from the GNN model.
    In production, these come from the SAGE layer neighbourhood aggregation."""
    # Simulated attention weights
    np.random.seed(hash(supplier_id) % 2**31)
    weights = np.random.dirichlet(np.ones(6))
    feature_names = [
        "weather_severity", "geopolitical_risk", "port_congestion",
        "financial_stress", "news_sentiment", "lead_time_variance",
    ]
    return dict(zip(feature_names, [round(w, 4) for w in weights]))


# ── Human-Readable Explanation ──────────────────────────────────────────────
def explain_risk(supplier_id: str, meta_features: dict = None) -> dict:
    """Generate human-readable risk explanation for a supplier.

    Returns overall risk score, confidence, and top-3 contributing factors
    with direction and magnitude, formatted as natural language strings.
    """
    # Load meta-learner
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "models", "meta_learner.joblib"
    )

    if meta_features is None:
        # Simulate sub-model outputs for demo
        np.random.seed(hash(supplier_id) % 2**31)
        meta_features = {
            "gnn_risk_score": round(np.random.beta(2, 5), 4),
            "tft_3day_forecast": round(np.random.beta(2, 5), 4),
            "tft_uncertainty": round(np.random.uniform(0.05, 0.3), 4),
            "geo_risk_score": round(np.random.choice([0.1, 0.5, 0.6, 0.7]), 4),
            "geo_risk_type_encoded": int(np.random.randint(0, 4)),
            "current_reliability_score": round(np.random.uniform(0.3, 1.0), 4),
            "tier": int(np.random.choice([1, 2, 3])),
        }

    X = pd.DataFrame([meta_features])[META_FEATURES]

    # Predict
    if os.path.exists(model_path):
        model = joblib.load(model_path)
        risk_prob = model.predict_proba(X)[0, 1]
        risk_class = int(model.predict(X)[0])
    else:
        # Fallback simple heuristic
        risk_prob = (
            0.35 * meta_features["gnn_risk_score"] +
            0.3 * meta_features["tft_3day_forecast"] +
            0.2 * meta_features["geo_risk_score"] +
            0.15 * (1 - meta_features["current_reliability_score"])
        )
        risk_class = int(risk_prob > 0.35)

    # SHAP explanation
    explanations = []
    if os.path.exists(model_path) and HAS_SHAP:
        model = joblib.load(model_path)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        shap_dict = dict(zip(META_FEATURES, shap_values[0]))

        # Sort by absolute SHAP value, pick top 3
        sorted_shap = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)[:3]

        FEATURE_LABELS = {
            "gnn_risk_score": "Network risk analysis",
            "tft_3day_forecast": "3-day forecast trending",
            "tft_uncertainty": "Forecast uncertainty",
            "geo_risk_score": "Satellite imagery",
            "geo_risk_type_encoded": "Geographic risk type",
            "current_reliability_score": "Supplier reliability",
            "tier": "Supply chain tier",
        }

        for feat, shap_val in sorted_shap:
            direction = "up" if shap_val > 0 else "down"
            label = FEATURE_LABELS.get(feat, feat)
            raw_val = meta_features[feat]

            if feat == "geo_risk_score":
                risk_types = ["Normal", "Flood_Risk", "Fire_Risk", "Infrastructure_Risk"]
                geo_type = risk_types[meta_features.get("geo_risk_type_encoded", 0)]
                explanations.append(
                    f"Satellite imagery shows {geo_type.replace('_', ' ').lower()} ({shap_val:+.2f})"
                )
            elif feat == "tft_3day_forecast":
                explanations.append(
                    f"{label} {direction} ({shap_val:+.2f})"
                )
            else:
                explanations.append(
                    f"{label} at {raw_val:.2f} ({shap_val:+.2f})"
                )
    else:
        # Fallback: rule-based explanation
        factors = [
            ("gnn_risk_score", meta_features["gnn_risk_score"], "Network risk analysis"),
            ("tft_3day_forecast", meta_features["tft_3day_forecast"], "3-day forecast"),
            ("geo_risk_score", meta_features["geo_risk_score"], "Satellite imagery risk"),
        ]
        factors.sort(key=lambda x: abs(x[1] - 0.3), reverse=True)
        for feat_name, val, label in factors[:3]:
            direction = "elevated" if val > 0.3 else "normal"
            explanations.append(f"{label} {direction} ({val:+.2f})")

    # GNN attention weights
    attention = compute_gnn_attention_weights(supplier_id)

    confidence = min(0.99, max(0.5, 1.0 - meta_features.get("tft_uncertainty", 0.15)))

    return {
        "supplier_id": supplier_id,
        "overall_risk_score": round(float(risk_prob), 4),
        "disruption_predicted": bool(risk_class),
        "confidence": round(confidence, 4),
        "top_3_reasons": explanations,
        "gnn_attention_weights": attention,
        "meta_features": meta_features,
    }


if __name__ == "__main__":
    model = train_meta_learner()

    # Demo explanation
    print("\n" + "=" * 60)
    print("Demo: explain_risk()")
    print("=" * 60)
    result = explain_risk("supplier_demo_001")
    print(json.dumps(result, indent=2, default=str))
