import os
import json
from datetime import datetime, timezone
from kafka import KafkaConsumer, KafkaProducer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys

# Allow importing from fastapi_app
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "fastapi_app"))
from models import RiskSignal
from database import SessionLocal
from id_utils import resolve_id

KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "localhost:9092")

def calculate_composite_score(weather, news, satellite):
    # Simple weighted average
    w_score = 0.5 if weather and weather.get('description') in ['storm', 'snow'] else 0.1
    n_score = (1 - news.get('sentiment_score', 0)) / 2 if news else 0.1
    s_score = satellite.get('risk_score', 0.1) if satellite else 0.1
    return 0.2 * w_score + 0.3 * n_score + 0.5 * s_score

def consume():
    consumer = KafkaConsumer(
        'raw.weather-events',
        'raw.news-events',
        'raw.satellite-signals',
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )

    state = {} # supplier_id -> {weather, news, satellite}
    db = SessionLocal()

    print("Listening for messages...")
    for message in consumer:
        try:
            topic = message.topic
            data = message.value
            supp_id = data.get('supplier_id')
            if not supp_id:
                continue
                
            if supp_id not in state:
                state[supp_id] = {'weather': None, 'news': None, 'satellite': None}
                
            if topic == 'raw.weather-events':
                state[supp_id]['weather'] = data
                rs = RiskSignal(supplier_id=resolve_id(supp_id), timestamp=datetime.fromisoformat(data['timestamp']), signal_type='weather', value=0.5 if data.get('description') in ['storm', 'snow'] else 0.1, source='OpenWeatherMap')
                db.add(rs)
            elif topic == 'raw.news-events':
                state[supp_id]['news'] = data
                rs = RiskSignal(supplier_id=resolve_id(supp_id), timestamp=datetime.fromisoformat(data['timestamp']), signal_type='news', value=(1 - data.get('sentiment_score', 0)) / 2, source='GDELT')
                db.add(rs)
            elif topic == 'raw.satellite-signals':
                state[supp_id]['satellite'] = data
                rs = RiskSignal(supplier_id=resolve_id(supp_id), timestamp=datetime.fromisoformat(data['timestamp']), signal_type='satellite', value=data.get('risk_score', 0), source='Satellite')
                db.add(rs)

            comp_score = calculate_composite_score(state[supp_id]['weather'], state[supp_id]['news'], state[supp_id]['satellite'])
            
            processed = {
                "supplier_id": supp_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "composite_score": comp_score
            }
            producer.send('processed.risk-scores', value=processed)
            
            rs_comp = RiskSignal(supplier_id=resolve_id(supp_id), timestamp=datetime.now(timezone.utc), signal_type='composite', value=comp_score, source='FlinkJob')
            db.add(rs_comp)
            db.commit()

        except Exception as e:
            print(f"Error processing message: {e}. Sending to DLQ...")
            try:
                failed_msg = str(getattr(message, 'value', ''))
                producer.send('dlq.raw-events', value={"error": str(e), "message": failed_msg})
                db.rollback()
            except Exception:
                db.rollback()

if __name__ == "__main__":
    consume()
