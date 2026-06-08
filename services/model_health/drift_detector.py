import numpy as np
import scipy.stats as stats
import json
import os
import time

def calculate_psi(expected: np.ndarray, actual: np.ndarray, num_buckets: int = 10) -> float:
    """Calculate Population Stability Index (PSI) between training (expected) and inference (actual) data."""
    def scale_by_total(arr):
        return arr / np.sum(arr)
        
    expected_pts = np.percentile(expected, np.linspace(0, 100, num_buckets + 1))
    # Adjust edge percentiles to handle boundary cases
    expected_pts[0] -= 1e-5
    expected_pts[-1] += 1e-5
    
    expected_pcts = np.histogram(expected, bins=expected_pts)[0]
    actual_pcts = np.histogram(actual, bins=expected_pts)[0]
    
    expected_pcts = scale_by_total(expected_pcts)
    actual_pcts = scale_by_total(actual_pcts)
    
    # Avoid zero division
    expected_pcts = np.where(expected_pcts == 0, 0.0001, expected_pcts)
    actual_pcts = np.where(actual_pcts == 0, 0.0001, actual_pcts)
    
    psi_value = np.sum((actual_pcts - expected_pcts) * np.log(actual_pcts / expected_pcts))
    return float(psi_value)

def detect_drift(current_scores: list, baseline_scores: list) -> dict:
    """Run KS-test and PSI to detect covariate/prediction drift."""
    curr_arr = np.array(current_scores)
    base_arr = np.array(baseline_scores)
    
    # 1. Kolmogorov-Smirnov Test
    ks_stat, p_value = stats.ks_2samp(curr_arr, base_arr)
    
    # 2. PSI
    psi_val = calculate_psi(base_arr, curr_arr)
    
    drift_detected = p_value < 0.05 or psi_val > 0.25
    
    results = {
        "timestamp": time.time(),
        "ks_statistic": float(ks_stat),
        "p_value": float(p_value),
        "psi_value": psi_val,
        "drift_detected": bool(drift_detected),
        "alert_level": "RED" if psi_val > 0.25 else ("YELLOW" if psi_val > 0.1 else "GREEN")
    }
    
    # Save log
    mlops_dir = os.path.dirname(__file__)
    logs_dir = os.path.join(mlops_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    with open(os.path.join(logs_dir, "drift_log.json"), "a") as f:
        f.write(json.dumps(results) + "\n")
        
    return results

if __name__ == "__main__":
    # Test script
    np.random.seed(42)
    baseline = np.random.beta(2, 5, 1000)
    # Simulate drifted scores (higher risk distribution)
    current = np.random.beta(3, 4, 1000)
    
    res = detect_drift(current.tolist(), baseline.tolist())
    print("Drift detection results:")
    print(json.dumps(res, indent=2))
