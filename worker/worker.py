import os
import sys
import time
import json
import datetime
import paho.mqtt.client as mqtt
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

# Add project root and API root to path to import API modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "api"))
from api.database import SessionLocal, engine
import api.models as models

import processing
import rules

# Read environment variables
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "worker")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "workerpass")

def get_db_session():
    return SessionLocal()

# --- MQTT Callbacks ---

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to Mosquitto Broker at {MQTT_HOST}:{MQTT_PORT}!")
        # Subscribe to telemetry and RINEX topics for all station IDs
        client.subscribe("sigap/+/telemetry")
        client.subscribe("sigap/+/rinex")
        print("Subscribed to sigap/+/telemetry and sigap/+/rinex")
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    topic_parts = msg.topic.split("/")
    if len(topic_parts) < 3:
        return
        
    station_id = topic_parts[1]
    message_type = topic_parts[2]
    
    db = get_db_session()
    try:
        # Autoregister station if it does not exist
        station = db.query(models.Station).filter(models.Station.id == station_id).first()
        if not station:
            print(f"Autoregistering new station: {station_id}")
            station = models.Station(
                id=station_id,
                name=station_id.capitalize(),
                type="rover",
                # default reference coordinates (Lereng Barat approximate as safety)
                reference_lat=-6.789123456,
                reference_lon=107.123456789,
                reference_height=1250.415,
                location="Area Pemantauan",
                peta_x=0.5,
                peta_y=0.5,
                last_heartbeat=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(station)
            db.commit()
            db.refresh(station)

        if message_type == "telemetry":
            # Process JSON live telemetry
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except Exception as e:
                print(f"Failed to decode telemetry JSON from {station_id}: {e}")
                return
                
            lat = payload.get("latitude")
            lon = payload.get("longitude")
            alt = payload.get("altitude_m")
            volt = payload.get("battery_voltage")
            sats = payload.get("satellites_active", 12)
            hdop = payload.get("hdop", 0.8)
            fix_type = payload.get("fix_type", "RTK_FIX")
            
            if lat is None or lon is None or alt is None:
                print(f"Telemetry missing coordinates from {station_id}")
                return

            print(f"Received live telemetry from {station_id}: Lat={lat:.8f}, Lon={lon:.8f}, Alt={alt:.3f}, Volt={volt}")

            # Calculate displacements relative to reference coordinates
            ref_lat = station.reference_lat
            ref_lon = station.reference_lon
            ref_alt = station.reference_height
            
            x, y, z = processing.lla_to_ecef(lat, lon, alt)
            east, north, up = processing.ecef_to_enu(x, y, z, ref_lat, ref_lon, ref_alt)

            # Insert position record
            now = datetime.datetime.now(datetime.timezone.utc)
            new_pos = models.Position(
                station_id=station_id,
                timestamp=now,
                latitude=lat,
                longitude=lon,
                height=alt,
                east_displacement=east,
                north_displacement=north,
                up_displacement=up,
                fix_type=fix_type,
                satellites=sats,
                hdop=hdop,
                battery_voltage=volt
            )
            db.add(new_pos)
            
            # Update last heartbeat
            station.last_heartbeat = now
            db.commit()
            
            # Run rule engine
            rules.evaluate_rules(db, station_id, new_pos)
            
        elif message_type == "rinex":
            # Process uploaded RINEX observation file
            print(f"Received RINEX file upload from {station_id} (Size: {len(msg.payload)} bytes)")
            
            # Save file to persistent storage path
            storage_dir = f"/app/storage/rinex/{station_id}"
            os.makedirs(storage_dir, exist_ok=True)
            
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"session_{timestamp_str}.obs"
            file_path = os.path.join(storage_dir, file_name)
            
            with open(file_path, "wb") as f:
                f.write(msg.payload)
                
            # Process RINEX file geodetics (approx or RTK)
            ref_lat = station.reference_lat
            ref_lon = station.reference_lon
            ref_alt = station.reference_height
            
            results = processing.process_rinex_file(file_path, ref_lat, ref_lon, ref_alt)
            
            # Create session record
            session_id = f"sess-{station_id}-{int(time.time())}"
            new_session = models.Session(
                id=session_id,
                station_id=station_id,
                session_start=results["start_time"],
                session_end=results["end_time"],
                status="done",
                rinex_path=file_path
            )
            db.add(new_session)
            db.commit()
            
            # Insert position record
            new_pos = models.Position(
                session_id=session_id,
                station_id=station_id,
                timestamp=results["end_time"], # Epoch of end session represents calculated coordinates
                latitude=results["latitude"],
                longitude=results["longitude"],
                height=results["height"],
                east_displacement=results["east_displacement"],
                north_displacement=results["north_displacement"],
                up_displacement=results["up_displacement"],
                fix_type=results["fix_type"],
                satellites=results["satellites"],
                hdop=results["hdop"],
                battery_voltage=results["battery_voltage"]
            )
            db.add(new_pos)
            
            # Update last heartbeat
            station.last_heartbeat = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            
            print(f"RINEX Session processed successfully: Session ID = {session_id}")
            
            # Run rule engine
            rules.evaluate_rules(db, station_id, new_pos)
            
    except Exception as e:
        print(f"Error handling message on {msg.topic}: {e}")
        db.rollback()
    finally:
        db.close()

# --- Scheduler Jobs ---

def heartbeat_job():
    db = get_db_session()
    try:
        rules.check_heartbeats(db)
    except Exception as e:
        print(f"Error in heartbeat check job: {e}")
    finally:
        db.close()

# --- Main Worker Loop ---

def main():
    print("Starting LowCostGNSS worker daemon...")
    
    # Wait for database container to be ready
    db_connected = False
    for i in range(10):
        try:
            db = get_db_session()
            db.execute(models.Base.metadata.tables["stations"].select())
            db.close()
            db_connected = True
            print("Successfully connected to the database!")
            break
        except Exception as e:
            print(f"Waiting for database... ({i+1}/10) - Error: {e}")
            time.sleep(3)
            
    if not db_connected:
        print("Could not connect to database. Exiting.")
        sys.exit(1)

    # Initialize scheduler for periodic heartbeat monitoring
    scheduler = BackgroundScheduler()
    scheduler.add_job(heartbeat_job, 'interval', seconds=10)
    scheduler.start()
    print("Scheduler started (running heartbeat job every 10s)")

    # Initialize MQTT client
    client = mqtt.Client(client_id="gnss_worker_service")
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    # Handle connection retries
    connected = False
    for i in range(10):
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            connected = True
            break
        except Exception as e:
            print(f"Waiting for Mosquitto Broker at {MQTT_HOST}:{MQTT_PORT}... ({i+1}/10) - Error: {e}")
            time.sleep(3)

    if not connected:
        print("Could not connect to Mosquitto Broker. Exiting.")
        sys.exit(1)

    # Start the network loop in blocking mode
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Stopping worker...")
        scheduler.shutdown()
        client.disconnect()

if __name__ == "__main__":
    main()
