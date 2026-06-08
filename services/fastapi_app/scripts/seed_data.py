import os
import sys
import uuid
import random
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import engine, IS_SQLITE
from models import Base, SupplierNode, SKUCatalog, SupplierSKULink, RiskSignal, DisruptionEvent

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

COUNTRIES = [
    "United States", "China", "Germany", "Japan", "India", "Vietnam", 
    "South Korea", "Taiwan", "Mexico", "Canada", "Netherlands", "Singapore"
]

DOMAINS = ["industry.com", "globalparts.net", "logistics.org", "supplies.co", "techmanufacturing.com"]

def seed_data():
    # Automatically build schema if SQLite
    if IS_SQLITE:
        print("Initializing SQLite tables...")
        Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    
    shared_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "data", "shared_ids.json"
    )
    
    if not os.path.exists(shared_file):
        print("Error: shared_ids.json does not exist. Run generate_shared_ids.py first.")
        return
        
    with open(shared_file, "r") as f:
        shared_data = json.load(f)

    # Check if we already have data
    if db.query(SupplierNode).count() > 0:
        print("Data already exists. Skipping seed.")
        db.close()
        return

    print("Seeding suppliers from shared_ids.json...")
    suppliers = []
    for s_info in shared_data["suppliers"]:
        # Random coordinates in reasonable bounding box or global range
        lat = random.uniform(-60.0, 75.0)
        lon = random.uniform(-180.0, 180.0)
        comp_name_slug = s_info["name"].lower().replace(" ", "")
        domain = random.choice(DOMAINS)
        email = f"contact@{comp_name_slug}.{domain}"
        
        raw_id = s_info["id"]
        supplier = SupplierNode(
            id=raw_id if IS_SQLITE else uuid.UUID(raw_id),
            name=s_info["name"],
            country=random.choice(COUNTRIES),
            tier=random.choice([1, 2, 3]),
            reliability_score=random.uniform(0.6, 1.0),
            geom=f'SRID=4326;POINT({lon} {lat})',
            metadata_col={"website": f"https://www.{comp_name_slug}.{domain}", "contact_email": email}
        )
        suppliers.append(supplier)
        db.add(supplier)
        
    db.commit()

    print("Seeding SKUs from shared_ids.json...")
    skus = []
    categories = ["Electronics", "Raw Materials", "Packaging", "Machinery", "Chemicals"]
    for sku_info in shared_data["skus"]:
        raw_sku_id = sku_info["id"]
        sku = SKUCatalog(
            id=raw_sku_id if IS_SQLITE else uuid.UUID(raw_sku_id),
            name=sku_info["name"],
            category=random.choice(categories),
            criticality_score=random.uniform(0.1, 1.0)
        )
        skus.append(sku)
        db.add(sku)
        
    db.commit()

    print("Seeding Supplier-SKU links...")
    for sku in skus:
        # Each SKU is supplied by 1-3 suppliers
        num_suppliers = random.randint(1, 3)
        chosen_suppliers = random.sample(suppliers, num_suppliers)
        for supp in chosen_suppliers:
            link = SupplierSKULink(
                supplier_id=supp.id,
                sku_id=sku.id,
                lead_time_days=random.randint(5, 60),
                capacity_units=random.randint(1000, 100000)
            )
            db.add(link)
            
    db.commit()

    # Seed Risk Signals
    print("Seeding risk signals for each supplier...")
    now = datetime.now(timezone.utc)
    for supp in suppliers:
        # GNN risk score
        db.add(RiskSignal(
            supplier_id=supp.id,
            timestamp=now,
            signal_type="gnn_risk_score",
            value=random.uniform(0.1, 0.8),
            source="GNN_Model"
        ))
        # TFT forecast
        db.add(RiskSignal(
            supplier_id=supp.id,
            timestamp=now,
            signal_type="tft_3day_forecast",
            value=random.uniform(0.1, 0.8),
            source="TFT_Forecaster"
        ))
        # Geo risk score
        db.add(RiskSignal(
            supplier_id=supp.id,
            timestamp=now,
            signal_type="geo_risk_score",
            value=random.uniform(0.0, 0.5),
            source="Satellite_Geo_Risk"
        ))
        
    db.commit()

    # Seed some Disruption Events
    print("Seeding disruption events...")
    for _ in range(5):
        affected = [str(random.choice(suppliers).id) for _ in range(random.randint(1, 3))]
        
        event = DisruptionEvent(
            id=str(uuid.uuid4()) if IS_SQLITE else uuid.uuid4(),
            occurred_at=now - timedelta(days=random.randint(1, 10)),
            event_type=random.choice(["Port Congestion", "Geopolitical Conflict", "Extreme Weather"]),
            severity=random.uniform(0.5, 0.95),
            affected_supplier_ids=affected if IS_SQLITE else [uuid.UUID(uid) for uid in affected],
            predicted=random.choice([True, False]),
            agent_action="Rerouted cargo to alternative ports",
            resolved_at=now - timedelta(days=random.randint(0, 5))
        )
        db.add(event)
        
    db.commit()
    print("Seed complete.")
    db.close()

if __name__ == "__main__":
    seed_data()
