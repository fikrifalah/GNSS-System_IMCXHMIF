import math
import datetime
from sqlalchemy.orm import Session
# We can import models directly from the api folder by adding it to sys.path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api.models as models

def evaluate_rules(db: Session, station_id: str, pos: models.Position):
    """
    Evaluates rule criteria based on the latest position reading and triggers/resolves alerts.
    """
    station = db.query(models.Station).filter(models.Station.id == station_id).first()
    if not station:
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    
    # -------------------------------------------------------------
    # 1. MOVEMENT ALERTS RULE
    # -------------------------------------------------------------
    east_mm = pos.east_displacement * 1000.0
    north_mm = pos.north_displacement * 1000.0
    up_mm = pos.up_displacement * 1000.0
    
    horizontal_mm = math.hypot(east_mm, north_mm)
    movement_indicator_mm = max(horizontal_mm, abs(up_mm))
    
    # Check if GNSS data is reliable for movement analysis
    data_terpercaya = pos.fix_type == "RTK_FIX" and pos.hdop <= 1.0 and pos.satellites >= 10
    
    if data_terpercaya:
        # Evaluate movement thresholds
        if movement_indicator_mm >= 50.0:
            # Trigger BAHAYA alert, resolve WASPADA alert
            trigger_alert(
                db, station_id, "BAHAYA",
                "Pergerakan melewati ambang bahaya",
                f"Indikator pergerakan {movement_indicator_mm:.1f} mm, di atas ambang prototipe 50 mm.",
                "Aturan prototipe prototype-movement-alarm-v1: indikator ≥ 50 mm bertahan minimal 3 detik. Ambang belum divalidasi ahli geoteknik. Bukan peringatan evakuasi."
            )
            resolve_alert(db, station_id, "Pergerakan memasuki ambang waspada")
        elif movement_indicator_mm >= 20.0:
            # Trigger WASPADA alert, resolve BAHAYA alert
            trigger_alert(
                db, station_id, "WASPADA",
                "Pergerakan memasuki ambang waspada",
                f"Indikator pergerakan {movement_indicator_mm:.1f} mm, berada pada rentang 20–50 mm.",
                "Aturan prototipe prototype-movement-alarm-v1: rentang waspada 20 mm sampai kurang dari 50 mm."
            )
            resolve_alert(db, station_id, "Pergerakan melewati ambang bahaya")
        else:
            # Safe range: resolve both
            resolve_alert(db, station_id, "Pergerakan melewati ambang bahaya")
            resolve_alert(db, station_id, "Pergerakan memasuki ambang waspada")
            
    # -------------------------------------------------------------
    # 2. GNSS DATA QUALITY RULE
    # -------------------------------------------------------------
    if not data_terpercaya:
        trigger_alert(
            db, station_id, "WASPADA",
            "Kualitas data GNSS tidak memenuhi syarat",
            f"Fix {pos.fix_type}, {pos.satellites} satelit, HDOP {pos.hdop:.1f}. Pengukuran tidak dipakai untuk menilai pergerakan.",
            "Aturan prototype-gnss-quality-rule-v1 menuntut RTK_FIX, HDOP ≤ 1.0 dan minimal 10 satelit. Status pergerakan menjadi Tidak Dapat Dinilai."
        )
    else:
        resolve_alert(db, station_id, "Kualitas data GNSS tidak memenuhi syarat")

    # -------------------------------------------------------------
    # 3. BATTERY VOLTAGE RULE
    # -------------------------------------------------------------
    if pos.battery_voltage is not None:
        v = pos.battery_voltage
        if v < 11.5:
            severity = "BAHAYA" if v < 10.8 else "WASPADA"
            trigger_alert(
                db, station_id, severity,
                "Tegangan baterai rendah",
                f"Tegangan {v:.1f} V berada di bawah ambang 11.5 V.",
                "Kesehatan perangkat terpisah dari status pergerakan. Ambang baterai masih sementara karena jenis baterai belum ditetapkan."
            )
        else:
            resolve_alert(db, station_id, "Tegangan baterai rendah")


def check_heartbeats(db: Session):
    """
    Scans for stations that haven't sent telemetries/heartbeats in over 60 seconds
    and creates alerts or resolves them.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    threshold_time = now - datetime.timedelta(seconds=60)
    
    # Query all rovers
    stations = db.query(models.Station).filter(models.Station.type == "rover").all()
    
    for s in stations:
        if s.last_heartbeat is None or s.last_heartbeat < threshold_time:
            # Device is offline
            # Calculate duration since last heartbeat
            duration_str = "lama"
            if s.last_heartbeat:
                diff = now - s.last_heartbeat
                hours, remainder = divmod(diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = f"{diff.days * 24 + hours} jam {minutes} menit lalu" if (diff.days * 24 + hours) > 0 else f"{minutes} menit lalu"
                
            trigger_alert(
                db, s.id, "WASPADA",
                "Perangkat tidak mengirim telemetri",
                f"Tidak ada data masuk sejak {duration_str}.",
                "Perangkat dianggap Offline setelah 10 detik tanpa telemetri pada prototipe. Nilai pergerakan terakhir tidak lagi mewakili kondisi sekarang."
            )
        else:
            # Device is online, resolve offline alert
            resolve_alert(db, s.id, "Perangkat tidak mengirim telemetri")


# --- Helper functions to create/resolve DB alerts ---

def trigger_alert(db: Session, station_id: str, severity: str, message: str, description: str, details: str):
    """
    Creates an alert in the database if an identical unresolved alert does not already exist.
    """
    # Check if there is an active alert with the same message
    active_alert = db.query(models.Alert).filter(
        models.Alert.station_id == station_id,
        models.Alert.message == message,
        models.Alert.resolved == False
    ).first()
    
    if active_alert:
        # If severity changed, update it, otherwise ignore
        if active_alert.severity != severity:
            active_alert.severity = severity
            active_alert.timestamp = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
        return

    # Create new alert
    alert_id = f"alm-{station_id}-{int(datetime.datetime.now().timestamp())}"
    new_alert = models.Alert(
        id=alert_id,
        station_id=station_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        severity=severity,
        message=message,
        description=description,
        details=details,
        resolved=False
    )
    db.add(new_alert)
    db.commit()
    print(f"ALERT TRIGGERED: [{severity}] {station_id} - {message}")


def resolve_alert(db: Session, station_id: str, message: str):
    """
    Marks any active alerts with the given message for a station as resolved.
    """
    active_alerts = db.query(models.Alert).filter(
        models.Alert.station_id == station_id,
        models.Alert.message == message,
        models.Alert.resolved == False
    ).all()
    
    if active_alerts:
        for a in active_alerts:
            a.resolved = True
        db.commit()
        print(f"ALERT RESOLVED: {station_id} - {message}")
