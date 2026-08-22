import os
import sys
import time
import math
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models
import schemas
from database import engine, SessionLocal, get_db

# Initialize FastAPI app
app = FastAPI(
    title="LowCostGNSS Monitoring API",
    description="Backend API for real-time ground deformation monitoring prototype",
    version="1.0.0"
)

# Configure CORS so the standalone HTML frontend can fetch from it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Security definition
API_KEY = os.getenv("API_KEY", "my_super_secret_api_key_123")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(header_key: str = Security(api_key_header)):
    if header_key == API_KEY:
        return header_key
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Akses ditolak: API Key tidak valid."
    )

# --- Seeding default data on startup ---
def seed_database():
    db = SessionLocal()
    try:
        # Check if stations exist
        if db.query(models.Station).count() > 0:
            return
        
        print("Seeding default stations and historical positions...")
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # 5 Default stations
        default_stations = [
            models.Station(
                id="rover-01", name="Rover-01", type="rover",
                reference_lat=-6.789123456, reference_lon=107.123456789, reference_height=1250.415,
                location="Lereng Barat", peta_x=0.27, peta_y=0.62, last_heartbeat=now
            ),
            models.Station(
                id="rover-02", name="Rover-02", type="rover",
                reference_lat=-6.788412330, reference_lon=107.126891004, reference_height=1243.882,
                location="Lereng Timur", peta_x=0.66, peta_y=0.34, last_heartbeat=now
            ),
            models.Station(
                id="rover-03", name="Rover-03", type="rover",
                reference_lat=-6.786901221, reference_lon=107.124773100, reference_height=1261.204,
                location="Puncak Utara", peta_x=0.45, peta_y=0.16, last_heartbeat=now
            ),
            models.Station(
                id="rover-04", name="Rover-04", type="rover",
                reference_lat=-6.791004778, reference_lon=107.125410990, reference_height=1218.760,
                location="Kaki Lereng", peta_x=0.58, peta_y=0.79, last_heartbeat=now - datetime.timedelta(hours=4)
            ),
            models.Station(
                id="rover-05", name="Rover-05", type="rover",
                reference_lat=-6.790233145, reference_lon=107.121880042, reference_height=1232.508,
                location="Jalur Air", peta_x=0.14, peta_y=0.30, last_heartbeat=now
            )
        ]
        
        for station in default_stations:
            db.add(station)
        db.commit()

        # Seed historical coordinates (96 points for last 24 hours)
        # to populate history charts immediately
        displacements = {
            "rover-01": (0.0021, -0.0004, 0.0002, "RTK_FIX", 19, 0.6, 12.4),
            "rover-02": (0.0473, 0.0336, -0.0128, "RTK_FIX", 16, 0.8, 11.3),
            "rover-03": (0.0084, -0.0051, 0.0019, "RTK_FLOAT", 7, 1.8, 12.1),
            "rover-04": (0.0217, 0.0092, -0.0034, "RTK_FIX", 14, 0.9, 10.6),
            "rover-05": (0.0180, 0.0160, -0.0041, "RTK_FIX", 12, 0.9, 12.0)
        }

        for st_id, (de, dn, du, fix, sats, hdop, volt) in displacements.items():
            st = db.query(models.Station).filter(models.Station.id == st_id).first()
            if not st:
                continue
            
            # Generate 96 historical records back in time
            for i in range(96):
                p = i / 95.0
                # Simulate a progressive movement trend over 24 hours
                t_de = de * (p ** 1.7) + (math.sin(p * 10) * 0.0002)
                t_dn = dn * (p ** 1.7) + (math.cos(p * 10) * 0.0002)
                t_du = du * (p ** 1.7) + (math.sin(p * 5) * 0.0001)
                
                pt_time = now - datetime.timedelta(hours=24) + datetime.timedelta(minutes=15 * i)
                if st_id == "rover-04" and pt_time > st.last_heartbeat:
                    continue # Do not add telemetry past its heartbeat for offline simulated rover
                
                pos = models.Position(
                    station_id=st_id,
                    timestamp=pt_time,
                    latitude=st.reference_lat + (t_dn / 111132.954),
                    longitude=st.reference_lon + (t_de / (111132.954 * math.cos(math.radians(st.reference_lat)))),
                    height=st.reference_height + t_du,
                    east_displacement=t_de,
                    north_displacement=t_dn,
                    up_displacement=t_du,
                    fix_type=fix,
                    satellites=sats,
                    hdop=hdop,
                    battery_voltage=volt
                )
                db.add(pos)
        
        # Seed default active alerts to match mock behavior
        default_alerts = [
            models.Alert(
                id="alm-02-gerak", station_id="rover-02", timestamp=now - datetime.timedelta(minutes=6),
                severity="BAHAYA", message="Pergerakan melewati ambang bahaya",
                description="Indikator pergerakan 57.3 mm, di atas ambang prototipe 50 mm.",
                details="Aturan prototipe prototype-movement-alarm-v1: indikator ≥ 50 mm bertahan minimal 3 detik. Ambang belum divalidasi ahli geoteknik. Bukan peringatan evakuasi.",
                resolved=False
            ),
            models.Alert(
                id="alm-02-baterai", station_id="rover-02", timestamp=now - datetime.timedelta(minutes=42),
                severity="WASPADA", message="Tegangan baterai rendah",
                description="Tegangan 11.3 V berada di bawah ambang 11.5 V selama lebih dari 30 detik.",
                details="Kesehatan perangkat terpisah dari status pergerakan. Ambang baterai masih sementara karena jenis baterai belum ditetapkan.",
                resolved=False
            ),
            models.Alert(
                id="alm-03-kualitas", station_id="rover-03", timestamp=now - datetime.timedelta(minutes=11),
                severity="WASPADA", message="Kualitas data GNSS tidak memenuhi syarat",
                description="Fix RTK_FLOAT, 7 satelit, HDOP 1.8. Pengukuran tidak dipakai untuk menilai pergerakan.",
                details="Aturan prototype-gnss-quality-rule-v1 menuntut RTK_FIX, HDOP ≤ 1.0 dan minimal 10 satelit. Status pergerakan menjadi Tidak Dapat Dinilai.",
                resolved=False
            ),
            models.Alert(
                id="alm-04-offline", station_id="rover-04", timestamp=now - datetime.timedelta(hours=3, minutes=57),
                severity="WASPADA", message="Perangkat tidak mengirim telemetri",
                description="Tidak ada data masuk sejak 3 jam 58 menit lalu. Baterai terakhir 10.6 V (kritis).",
                details="Perangkat dianggap Offline setelah 10 detik tanpa telemetri pada prototipe. Nilai pergerakan terakhir tidak lagi mewakili kondisi sekarang.",
                resolved=False
            ),
            models.Alert(
                id="alm-05-gerak", station_id="rover-05", timestamp=now - datetime.timedelta(minutes=27),
                severity="WASPADA", message="Pergerakan memasuki ambang waspada",
                description="Indikator pergerakan 24.1 mm, berada pada rentang 20–50 mm.",
                details="Aturan prototipe prototype-movement-alarm-v1: rentang waspada 20 mm sampai kurang dari 50 mm.",
                resolved=False
            )
        ]
        
        for alert in default_alerts:
            db.add(alert)
            
        db.commit()
        print("Database seeded successfully.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    # Make sure tables are created (fallback in case migrations are not run yet)
    db_connected = False
    for i in range(20):
        try:
            models.Base.metadata.create_all(bind=engine)
            db_connected = True
            print("Successfully connected to the database and created tables!")
            break
        except Exception as e:
            print(f"API waiting for database... ({i+1}/20) - Error: {e}")
            time.sleep(2)
            
    if not db_connected:
        print("API could not connect to database. Exiting.")
        sys.exit(1)
        
    seed_database()

# --- API Endpoints ---

@app.get("/api/dashboard", response_model=schemas.DashboardResponse)
def get_dashboard(jumlahRover: int = 5, kondisi: str = "normal", db: Session = Depends(get_db)):
    now_ms = int(time.time() * 1000)
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    
    if kondisi == "galat":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gagal menghubungi layanan data (HTTP 502)."
        )
        
    if kondisi == "kosong":
        return schemas.DashboardResponse(
            mode="LIVE",
            lokasi=schemas.LokasiSchema(
                nama="Lokasi Uji Cisarua", status="TIDAK_DAPAT_DINILAI",
                rover_total=0, online=0, offline=0, alarm_aktif=0,
                ts_terbaru=None, basi=False
            ),
            rovers=[], alarms=[], diambil_pada=now_ms
        )

    # Fetch rovers limit to jumlahRover
    stations = db.query(models.Station).filter(models.Station.type == "rover").limit(jumlahRover).all()
    
    rovers_list = []
    active_station_ids = [s.id for s in stations]
    
    for i, s in enumerate(stations):
        # Fetch latest position
        latest_pos = db.query(models.Position).filter(models.Position.station_id == s.id).order_by(models.Position.timestamp.desc()).first()
        
        if not latest_pos:
            continue
            
        # Extract variables
        east_mm = round(latest_pos.east_displacement * 1000, 1)
        north_mm = round(latest_pos.north_displacement * 1000, 1)
        up_mm = round(latest_pos.up_displacement * 1000, 1)
        
        horizontal_mm = round(math.hypot(east_mm, north_mm), 1)
        displacement_3d_mm = round(math.hypot(east_mm, north_mm, up_mm), 1)
        movement_indicator_mm = round(max(horizontal_mm, abs(up_mm)), 1)
        
        ts_ms = int(latest_pos.timestamp.timestamp() * 1000)
        
        # Override values for conditions simulating specific test cases
        fix_type = latest_pos.fix_type
        satellites_active = latest_pos.satellites
        hdop = latest_pos.hdop
        battery_voltage = latest_pos.battery_voltage or 12.0
        
        if kondisi == "offline" and i == 0:
            ts_ms = now_ms - 12 * 60 * 1000 # 12 minutes old
        elif kondisi == "gnss" and i == 0:
            fix_type = "RTK_FLOAT"
            satellites_active = 7
            hdop = 1.8
        elif kondisi == "kedaluwarsa":
            ts_ms = now_ms - 9 * 60 * 1000 # 9 minutes old

        # Calculate states
        online = (now_ms - ts_ms) < 60 * 1000
        data_terpercaya = fix_type == "RTK_FIX" and hdop <= 1.0 and satellites_active >= 10
        
        if not data_terpercaya or not online:
            movement_status = "TIDAK_DAPAT_DINILAI"
        elif movement_indicator_mm >= 50:
            movement_status = "BAHAYA"
        elif movement_indicator_mm >= 20:
            movement_status = "WASPADA"
        else:
            movement_status = "AMAN"
            
        battery_status = "KRITIS" if battery_voltage < 10.8 else "RENDAH" if battery_voltage < 11.5 else "NORMAL"
        
        rovers_list.append(schemas.RoverSchema(
            deviceId=s.id,
            nama=s.name,
            lokasi=s.location or "Lereng",
            ts=ts_ms,
            latitude=latest_pos.latitude,
            longitude=latest_pos.longitude,
            altitude_m=latest_pos.height,
            east_mm=east_mm,
            north_mm=north_mm,
            up_mm=up_mm,
            horizontal_mm=horizontal_mm,
            displacement_3d_mm=displacement_3d_mm,
            movement_indicator_mm=movement_indicator_mm,
            movement_status=movement_status,
            connectivity_status="ONLINE" if online else "OFFLINE",
            battery_status=battery_status,
            battery_voltage=battery_voltage,
            fix_type=fix_type,
            satellites_active=satellites_active,
            hdop=hdop,
            data_terpercaya=data_terpercaya,
            peta=schemas.MapPosition(x=s.peta_x or 0.5, y=s.peta_y or 0.5)
        ))

    # Fetch active alerts for only the active rovers
    db_alerts = db.query(models.Alert).filter(
        models.Alert.station_id.in_(active_station_ids),
        models.Alert.resolved == False
    ).all()
    
    # Map alerts
    alarms_list = []
    for a in db_alerts:
        alarms_list.append(schemas.AlarmSchema(
            id=a.id,
            severity=a.severity,
            deviceId=a.station_id,
            rover=db.query(models.Station.name).filter(models.Station.id == a.station_id).scalar() or "Rover",
            ts=int(a.timestamp.timestamp() * 1000),
            judul=a.message,
            deskripsi=a.description or "",
            detail=a.details or "",
            status="AKTIF"
        ))
        
    # Sort alarms by severity (BAHAYA first) and timestamp descending
    severity_order = {"BAHAYA": 0, "WASPADA": 1, "INFORMASI": 2}
    alarms_list.sort(key=lambda x: (severity_order.get(x.severity, 3), -x.ts))
    
    # Calculate Location status
    if any(r.movement_status == "BAHAYA" for r in rovers_list):
        loc_status = "BAHAYA"
    elif any(r.movement_status == "WASPADA" for r in rovers_list):
        loc_status = "WASPADA"
    elif all(r.movement_status == "AMAN" for r in rovers_list) and rovers_list:
        loc_status = "AMAN"
    else:
        loc_status = "TIDAK_DAPAT_DINILAI"
        
    ts_terbaru = max([r.ts for r in rovers_list]) if rovers_list else None
    basi = ts_terbaru is not None and (now_ms - ts_terbaru) > 5 * 60 * 1000
    
    online_count = sum(1 for r in rovers_list if r.connectivity_status == "ONLINE")
    offline_count = sum(1 for r in rovers_list if r.connectivity_status == "OFFLINE")

    return schemas.DashboardResponse(
        mode="LIVE",
        lokasi=schemas.LokasiSchema(
            nama="Lokasi Uji Cisarua",
            status=loc_status,
            rover_total=len(rovers_list),
            online=online_count,
            offline=offline_count,
            alarm_aktif=len(alarms_list),
            ts_terbaru=ts_terbaru,
            basi=basi
        ),
        rovers=rovers_list,
        alarms=alarms_list,
        diambil_pada=now_ms
    )


@app.get("/api/history", response_model=schemas.HistoryResponse)
def get_history(deviceId: str, rentang: str = "24j", db: Session = Depends(get_db)):
    rentang_map = {
        "1j": datetime.timedelta(hours=1),
        "6j": datetime.timedelta(hours=6),
        "24j": datetime.timedelta(hours=24),
        "7h": datetime.timedelta(days=7),
        "30h": datetime.timedelta(days=30)
    }
    
    time_delta = rentang_map.get(rentang, datetime.timedelta(hours=24))
    cutoff_time = datetime.datetime.now(datetime.timezone.utc) - time_delta
    
    # Query position records in the time range
    points = db.query(models.Position).filter(
        models.Position.station_id == deviceId,
        models.Position.timestamp >= cutoff_time
    ).order_by(models.Position.timestamp.asc()).all()
    
    if not points:
        # Fallback to last 96 points in case no data matches the specific time query
        points = db.query(models.Position).filter(
            models.Position.station_id == deviceId
        ).order_by(models.Position.timestamp.desc()).limit(96).all()
        points.reverse() # Back to chronological order
        
    history_points = []
    for p in points:
        history_points.append(schemas.HistoryPoint(
            ts=int(p.timestamp.timestamp() * 1000),
            east_mm=round(p.east_displacement * 1000, 2),
            north_mm=round(p.north_displacement * 1000, 2),
            up_mm=round(p.up_displacement * 1000, 2)
        ))
        
    # Calculate interval minutes
    if len(history_points) > 1:
        span_min = (history_points[-1].ts - history_points[0].ts) / (60 * 1000)
        interval_menit = max(1, round(span_min / len(history_points)))
    else:
        interval_menit = 15

    return schemas.HistoryResponse(
        deviceId=deviceId,
        rentang=rentang,
        satuan="mm",
        interval_menit=interval_menit,
        titik=history_points
    )

# --- Administrative Endpoints ---

@app.post("/api/stations", response_model=schemas.StationResponse)
def create_station(station: schemas.StationCreate, db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    db_station = db.query(models.Station).filter(models.Station.id == station.id).first()
    if db_station:
        # Update existing
        db_station.name = station.name
        db_station.type = station.type
        db_station.reference_lat = station.reference_lat
        db_station.reference_lon = station.reference_lon
        db_station.reference_height = station.reference_height
        db_station.location = station.location
        db_station.peta_x = station.peta_x
        db_station.peta_y = station.peta_y
    else:
        # Create new
        db_station = models.Station(
            id=station.id,
            name=station.name,
            type=station.type,
            reference_lat=station.reference_lat,
            reference_lon=station.reference_lon,
            reference_height=station.reference_height,
            location=station.location,
            peta_x=station.peta_x,
            peta_y=station.peta_y,
            last_heartbeat=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(db_station)
        
    db.commit()
    db.refresh(db_station)
    return db_station


@app.post("/api/simulasi-alarm")
def create_simulated_alarm(deviceId: str, severity: str = "WASPADA", db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    station = db.query(models.Station).filter(models.Station.id == deviceId).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station tidak ditemukan.")
        
    now = datetime.datetime.now(datetime.timezone.utc)
    alert_id = f"alm-{deviceId}-{int(time.time())}"
    
    alert = models.Alert(
        id=alert_id,
        station_id=deviceId,
        timestamp=now,
        severity=severity,
        message=f"Simulasi Alarm {severity}",
        description=f"Ini adalah peringatan simulasi {severity} untuk {station.name}.",
        details="Detail peringatan disimulasikan dari panel administrasi. Silakan selesaikan jika tidak diperlukan lagi.",
        resolved=False
    )
    
    db.add(alert)
    db.commit()
    return {"status": "success", "alert_id": alert_id}


@app.post("/api/simulasi-clear")
def clear_simulated_alarms(deviceId: str, db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    db.query(models.Alert).filter(
        models.Alert.station_id == deviceId,
        models.Alert.resolved == False
    ).update({models.Alert.resolved: True})
    db.commit()
    return {"status": "success", "message": f"Semua alarm untuk {deviceId} telah di-resolve."}


@app.get("/", response_class=HTMLResponse)
def read_root():
    html_path = "LowCostGNSS Pemantauan.html"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    # Check parent directory fallback
    parent_path = os.path.join("..", html_path)
    if os.path.exists(parent_path):
        with open(parent_path, "r", encoding="utf-8") as f:
            return f.read()
            
    return "<h3>LowCostGNSS Pemantauan.html not found! Please ensure it is mounted or generated.</h3>"

