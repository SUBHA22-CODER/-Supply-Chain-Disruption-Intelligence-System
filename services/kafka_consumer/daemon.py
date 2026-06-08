import os
import sys
import json
import uuid
from datetime import datetime, timezone
from kafka import KafkaConsumer, KafkaProducer

# Inject paths
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "fastapi_app"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent"))

from database import SessionLocal
from models import RiskSignal, DisruptionEvent, SupplierNode
from agent import AgentRunner
from id_utils import resolve_id
from schemas import WeatherEvent, NewsEvent, SatelliteSignal

KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "localhost:9092")
CONSUMER_TOPICS = ['raw.weather-events', 'raw.news-events', 'raw.satellite-signals']
DLQ_TOPIC = 'dlq.disruption-alerts'

# Schema validators per topic
_TOPIC_SCHEMAS = {
    'raw.weather-events': WeatherEvent,
    'raw.news-events': NewsEvent,
    'raw.satellite-signals': SatelliteSignal,
}

def get_consumer():
    return KafkaConsumer(
        *CONSUMER_TOPICS,
        bootstrap_servers=[KAFKA_BROKER],
        group_id='supplychain-consumer-group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        auto_offset_reset='latest'
    )

def get_dlq_producer():
    return KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )

def process_message(msg, db_session):
    topic = msg.topic
    payload = msg.value

    # Validate payload against Pydantic schema
    schema_cls = _TOPIC_SCHEMAS.get(topic)
    if schema_cls:
        validated = schema_cls(**payload)  # Raises ValidationError on bad data
        payload = validated.model_dump()   # Use validated + coerced values

    supplier_id_str = payload.get("supplier_id")
    
    if not supplier_id_str:
        raise ValueError("Missing supplier_id in message payload")
        
    supplier_uuid = resolve_id(supplier_id_str)
    
    # Verify supplier exists in database
    supplier = db_session.query(SupplierNode).filter(SupplierNode.id == supplier_uuid).first()
    if not supplier:
        raise ValueError(f"Supplier {supplier_id_str} not found in database.")

    timestamp = datetime.fromisoformat(payload.get("timestamp", datetime.now(timezone.utc).isoformat()))
    
    # Translate Kafka payload to Database RiskSignal
    if topic == 'raw.weather-events':
        # Translate weather into risk score (high wind/temp variance = high risk)
        temp = payload.get("temp", 20)
        wind = payload.get("wind_speed", 10)
        desc = payload.get("description", "clear")
        
        weather_val = 0.1
        if desc in ["storm", "snow"]:
            weather_val += 0.4
        if wind > 60:
            weather_val += 0.3
            
        signal = RiskSignal(
            supplier_id=supplier_uuid,
            timestamp=timestamp,
            signal_type="weather_risk",
            value=min(1.0, weather_val),
            source="Kafka_Weather_Stream"
        )
        db_session.add(signal)
        
    elif topic == 'raw.news-events':
        sentiment = payload.get("sentiment_score", 0.0)
        # Low sentiment (negative) implies higher risk
        news_val = min(1.0, max(0.0, (1.0 - sentiment) / 2))
        
        signal = RiskSignal(
            supplier_id=supplier_uuid,
            timestamp=timestamp,
            signal_type="news_risk",
            value=news_val,
            source="Kafka_News_Stream"
        )
        db_session.add(signal)
        
    elif topic == 'raw.satellite-signals':
        risk_score = payload.get("risk_score", 0.0)
        
        signal = RiskSignal(
            supplier_id=supplier_uuid,
            timestamp=timestamp,
            signal_type="geo_risk_score",
            value=risk_score,
            source="Kafka_Satellite_Stream"
        )
        db_session.add(signal)
        
        # If satellite risk is high, log a disruption event and run LangGraph Agent!
        if risk_score > 0.6:
            event = DisruptionEvent(
                occurred_at=timestamp,
                event_type="Geospatial Anomaly",
                severity=risk_score,
                affected_supplier_ids=[supplier_uuid],
                predicted=True
            )
            db_session.add(event)
            db_session.commit()
            
            print(f"Triggering LangGraph agent for high risk event on supplier {supplier_id_str}...")
            try:
                AgentRunner.run_for_supplier(supplier_id_str)
            except Exception as agent_err:
                print(f"Failed to execute LangGraph agent: {agent_err}")

    db_session.commit()

def main():
    print("Starting Kafka Consumer Daemon...")
    consumer = get_consumer()
    dlq_producer = get_dlq_producer()
    
    for msg in consumer:
        print(f"Received message from topic: {msg.topic}")
        db_session = SessionLocal()
        try:
            process_message(msg, db_session)
        except Exception as e:
            print(f"Error processing message from topic {msg.topic}: {e}")
            db_session.rollback()
            # Publish message to DLQ
            try:
                error_payload = {
                    "original_topic": msg.topic,
                    "payload": msg.value,
                    "error": str(e),
                    "failed_at": datetime.now(timezone.utc).isoformat()
                }
                dlq_producer.send(DLQ_TOPIC, value=error_payload)
                dlq_producer.flush()
                print("Successfully published failed message to DLQ.")
            except Exception as dlq_err:
                print(f"Failed to send to DLQ: {dlq_err}")
        finally:
            db_session.close()

if __name__ == "__main__":
    main()
