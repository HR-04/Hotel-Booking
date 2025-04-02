import psycopg2
import select
import threading
import pandas as pd
import random
import logging
from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine

router = APIRouter()
logger = logging.getLogger(__name__)

# Shared engine using the same DB_CONFIG from rag.py for consistency
DB_CONFIG = {
    "dbname": "hotel_db",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
engine = create_engine(DATABASE_URL)

@router.post("/generate-data")
async def generate_new_data():
    try:
        hotels = ["Resort Hotel", "City Hotel"]
        new_record = {
            "hotel": random.choice(hotels),
            "is_canceled": random.choice([0, 1]),
            "lead_time": random.randint(1, 200),
            "arrival_date_year": random.choice([2015, 2016, 2017]),
            "arrival_date_month": random.choice([
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]),
            "adr": round(random.uniform(50, 300), 2),
            "stays_in_week_nights": random.randint(0, 10),
            "stays_in_weekend_nights": random.randint(0, 5),
            "country": random.choice(["PRT", "GBR", "USA", "FRA", "ESP"])
        }
        new_record["revenue"] = new_record["adr"] * (new_record["stays_in_week_nights"] + new_record["stays_in_weekend_nights"])
        pd.DataFrame([new_record]).to_sql("hotel_bookings", con=engine, if_exists="append", index=False)
        logger.info(f"Inserted new record: {new_record}")
        return {"message": "New data record generated successfully."}
    except Exception as e:
        logger.error(f"Error generating new data: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate new data.")

def listen_to_notifications():
    try:
        conn = psycopg2.connect(
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"]
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("LISTEN new_data;")
        logger.info("Listening for new data notifications on channel 'new_data'...")
        while True:
            if select.select([conn], [], [], 5) == ([], [], []):
                continue
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                logger.info("Received notification: " + notify.payload)
                from rag import update_insights  # update insights on notification
                update_insights()
    except Exception as e:
        logger.error(f"Notification listener error: {e}")

def start_notification_listener():
    listener_thread = threading.Thread(target=listen_to_notifications, daemon=True)
    listener_thread.start()
    logger.info("Notification listener thread started.")
