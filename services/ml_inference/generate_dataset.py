"""
Task 05: Synthetic disruption dataset generation.

Generates an 18-month daily time series for 50 suppliers with realistic
features and disruption labels (~4% class imbalance). Saves as parquet.
"""
import os
import uuid
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

NUM_SUPPLIERS = 50
DAYS = 547  # ~18 months
START_DATE = datetime(2024, 1, 1)
DISRUPTION_RATE = 0.04  # 4% of rows

# Supplier metadata
COUNTRIES = ["India", "China", "USA", "Germany", "Brazil", "Japan", "Vietnam", "Mexico", "UK", "South Korea"]
REGIONS = {
    "India": "Asia", "China": "Asia", "Japan": "Asia", "Vietnam": "Asia", "South Korea": "Asia",
    "USA": "Americas", "Brazil": "Americas", "Mexico": "Americas",
    "Germany": "Europe", "UK": "Europe",
}

DISRUPTION_TYPES = ["flood", "strike", "port_closure", "financial", None]


def _seasonal_weather(day_of_year: int, country: str) -> float:
    """Weather severity follows seasonal patterns."""
    # Monsoon peaks in Asia mid-year, winter storms in Europe/Americas late year
    if REGIONS.get(country) == "Asia":
        base = 0.3 + 0.4 * np.sin(2 * np.pi * (day_of_year - 120) / 365)
    else:
        base = 0.2 + 0.3 * np.sin(2 * np.pi * (day_of_year - 300) / 365)
    return np.clip(base + np.random.normal(0, 0.08), 0, 1)


def _geopolitical_risk(day_index: int, region: str, regional_shocks: dict) -> float:
    """Geopolitical risk has regional correlation."""
    base = 0.15 + 0.05 * np.sin(2 * np.pi * day_index / 365)
    # Inject regional shocks
    if region in regional_shocks and day_index in regional_shocks[region]:
        base += random.uniform(0.3, 0.6)
    return np.clip(base + np.random.normal(0, 0.05), 0, 1)


def _generate_regional_shocks() -> dict:
    """Create correlated regional shock events."""
    shocks = {}
    for region in set(REGIONS.values()):
        shock_days = sorted(random.sample(range(DAYS), k=random.randint(3, 8)))
        expanded = set()
        for d in shock_days:
            for offset in range(random.randint(5, 20)):
                if d + offset < DAYS:
                    expanded.add(d + offset)
        shocks[region] = expanded
    return shocks


def generate_dataset() -> pd.DataFrame:
    """Generate the full synthetic dataset."""
    print("Generating synthetic disruption dataset...")

    regional_shocks = _generate_regional_shocks()
    rows = []

    suppliers = []
    for i in range(NUM_SUPPLIERS):
        country = random.choice(COUNTRIES)
        suppliers.append({
            "supplier_id": str(uuid.uuid4()),
            "country": country,
            "region": REGIONS[country],
            "tier": random.choice([1, 1, 2, 2, 2, 3, 3, 3, 3, 3]),  # weighted towards tier 3
            "base_lead_time": random.randint(7, 45),
        })

    # Pre-compute tier-1 disruption cascade schedule
    tier1_suppliers = [s for s in suppliers if s["tier"] == 1]
    tier2_suppliers = [s for s in suppliers if s["tier"] == 2]
    cascade_events = {}  # day -> list of affected tier-2 supplier indices
    for t1 in tier1_suppliers:
        # Each tier-1 disruption causes tier-2 disruptions within 7 days
        disruption_days = sorted(random.sample(range(DAYS), k=random.randint(1, 3)))
        for d in disruption_days:
            affected = random.sample(tier2_suppliers, k=min(3, len(tier2_suppliers)))
            for offset in range(1, 8):
                target_day = d + offset
                if target_day < DAYS:
                    if target_day not in cascade_events:
                        cascade_events[target_day] = []
                    cascade_events[target_day].extend([a["supplier_id"] for a in affected])

    for supplier in suppliers:
        sid = supplier["supplier_id"]
        country = supplier["country"]
        region = supplier["region"]
        tier = supplier["tier"]
        base_lt = supplier["base_lead_time"]

        # Track state for early warning signal injection
        disruption_scheduled = set()

        # Pre-decide disruption days for this supplier (~4%)
        num_disruptions = max(1, int(DAYS * DISRUPTION_RATE * random.uniform(0.5, 1.5)))
        raw_disruption_days = sorted(random.sample(range(30, DAYS), k=num_disruptions))

        # Add cascade-triggered disruptions for tier-2
        if tier == 2:
            for d in range(DAYS):
                if d in cascade_events and sid in cascade_events[d]:
                    raw_disruption_days.append(d)
            raw_disruption_days = sorted(set(raw_disruption_days))

        disruption_scheduled = set(raw_disruption_days)

        for day_idx in range(DAYS):
            date = START_DATE + timedelta(days=day_idx)
            doy = date.timetuple().tm_yday

            # --- Features ---
            weather = _seasonal_weather(doy, country)
            geo_risk = _geopolitical_risk(day_idx, region, regional_shocks)
            port_congestion = np.clip(0.2 + 0.15 * np.sin(2 * np.pi * day_idx / 180) + np.random.normal(0, 0.06), 0, 1)
            financial_stress = np.clip(np.random.beta(2, 8) + (0.15 if geo_risk > 0.5 else 0), 0, 1)
            news_sentiment = np.clip(np.random.normal(0.1, 0.25), -1, 1)
            lead_time_var = np.random.normal(0, base_lt * 0.15)

            # --- Early warning: elevate features 3-14 days before disruption ---
            days_to_next_disruption = None
            for dd in raw_disruption_days:
                if dd > day_idx:
                    days_to_next_disruption = dd - day_idx
                    break

            if days_to_next_disruption is not None and 3 <= days_to_next_disruption <= 14:
                warning_strength = 1.0 - (days_to_next_disruption - 3) / 11.0
                weather += warning_strength * random.uniform(0.1, 0.3)
                port_congestion += warning_strength * random.uniform(0.05, 0.2)
                financial_stress += warning_strength * random.uniform(0.05, 0.15)
                news_sentiment -= warning_strength * random.uniform(0.1, 0.4)
                lead_time_var += warning_strength * random.uniform(1, 5)

            weather = np.clip(weather, 0, 1)
            port_congestion = np.clip(port_congestion, 0, 1)
            financial_stress = np.clip(financial_stress, 0, 1)
            news_sentiment = np.clip(news_sentiment, -1, 1)

            # --- Labels ---
            is_disruption = day_idx in disruption_scheduled
            if is_disruption:
                d_type = random.choice(["flood", "strike", "port_closure", "financial"])
                d_severity = random.uniform(0.4, 1.0)
            else:
                d_type = None
                d_severity = 0.0

            rows.append({
                "date": date,
                "supplier_id": sid,
                "tier": tier,
                "country": country,
                "region": region,
                "weather_severity": round(weather, 4),
                "geopolitical_risk": round(geo_risk, 4),
                "port_congestion": round(port_congestion, 4),
                "financial_stress": round(financial_stress, 4),
                "news_sentiment": round(news_sentiment, 4),
                "lead_time_variance": round(lead_time_var, 4),
                "disruption_occurred": int(is_disruption),
                "disruption_type": d_type,
                "disruption_severity": round(d_severity, 4),
            })

    df = pd.DataFrame(rows)

    # Temporal train/val/test split (no leakage)
    split1 = START_DATE + timedelta(days=int(DAYS * 0.7))
    split2 = START_DATE + timedelta(days=int(DAYS * 0.85))
    df["split"] = "train"
    df.loc[df["date"] >= split1, "split"] = "val"
    df.loc[df["date"] >= split2, "split"] = "test"

    return df


def print_stats(df: pd.DataFrame) -> None:
    """Print dataset diagnostics."""
    print(f"\n{'='*60}")
    print(f"Dataset shape: {df.shape}")
    print(f"Suppliers: {df['supplier_id'].nunique()}")
    print(f"Date range: {df['date'].min()} -> {df['date'].max()}")
    print(f"\n--- Class Distribution ---")
    print(df["disruption_occurred"].value_counts(normalize=True).to_string())
    print(f"\n--- Split Sizes ---")
    print(df["split"].value_counts().to_string())
    print(f"\n--- Feature Correlations with disruption_occurred ---")
    feat_cols = ["weather_severity", "geopolitical_risk", "port_congestion",
                 "financial_stress", "news_sentiment", "lead_time_variance"]
    for c in feat_cols:
        corr = df[c].corr(df["disruption_occurred"])
        print(f"  {c:30s} {corr:+.4f}")
    print(f"\n--- Sample Rows ---")
    print(df.head(5).to_string(index=False))
    print(f"{'='*60}\n")


if __name__ == "__main__":
    df = generate_dataset()

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "processed")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "disruption_dataset.parquet")
    df.to_parquet(out_path, index=False)
    print(f"Saved to {out_path}")

    print_stats(df)
