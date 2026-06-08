"""
Kafka mock producers for testing the streaming pipeline.
Reads real supplier IDs from shared_ids.json to ensure messages
are processable by the consumer daemon and Flink jobs.
"""
import os
import json
import time
import random
from datetime import datetime, timezone
from kafka import KafkaProducer

KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "localhost:9092")

def _load_supplier_ids() -> list:
    """Load real supplier IDs from the shared_ids.json seed file."""
    shared_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "shared_ids.json"
    )
    if os.path.exists(shared_file):
        with open(shared_file, "r") as f:
            data = json.load(f)
        return [s["id"] for s in data["suppliers"][:10]]  # Use first 10 suppliers
    # Fallback to hardcoded UUIDs if file not found
    import uuid
    return [str(uuid.uuid4()) for _ in range(5)]

SUPPLIER_IDS = _load_supplier_ids()

def get_producer():
    return KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )

def poll_weather(producer):
    print(f"Polling Weather API for {len(SUPPLIER_IDS)} suppliers...")
    for supp_id in SUPPLIER_IDS:
        event = {
            "supplier_id": supp_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "temp": round(random.uniform(-10, 45), 1),
            "description": random.choice(["clear", "rain", "storm", "snow"]),
            "wind_speed": round(random.uniform(0, 100), 1)
        }
        producer.send('raw.weather-events', value=event)

def poll_news(producer):
    print(f"Polling News API for {len(SUPPLIER_IDS)} suppliers...")
    for supp_id in SUPPLIER_IDS:
        if random.random() > 0.5:  # 50% chance of news
            event = {
                "supplier_id": supp_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "keyword": random.choice(["strike", "fire", "bankruptcy", "shortage"]),
                "sentiment_score": round(random.uniform(-1.0, 1.0), 4)
            }
            producer.send('raw.news-events', value=event)

def poll_satellite(producer):
    print(f"Polling Satellite Signals for {len(SUPPLIER_IDS)} suppliers...")
    for supp_id in SUPPLIER_IDS:
        # Occasional spikes to trigger agent
        risk = random.uniform(0.0, 0.3) if random.random() > 0.1 else random.uniform(0.7, 1.0)
        event = {
            "supplier_id": supp_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "risk_score": round(risk, 4)
        }
        producer.send('raw.satellite-signals', value=event)

def main():
    producer = get_producer()
    print(f"Starting Kafka mock producers with {len(SUPPLIER_IDS)} suppliers...")
    while True:
        poll_weather(producer)
        poll_news(producer)
        poll_satellite(producer)
        producer.flush()
        print("Batch sent. Sleeping for 5 minutes...")
        time.sleep(300)

if __name__ == "__main__":
    main()
