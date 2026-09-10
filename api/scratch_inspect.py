from database import SessionLocal
import models

db = SessionLocal()
try:
    stations = db.query(models.Station).all()
    print("STATIONS:")
    for st in stations:
        print(f"ID: {st.id}, Name: {st.name}, Ref: {st.reference_lat}, {st.reference_lon}, {st.reference_height}")
        
        # Get last 2 positions
        positions = db.query(models.Position).filter(models.Position.station_id == st.id).order_by(models.Position.timestamp.desc()).limit(2).all()
        for p in positions:
            print(f"  Pos ID: {p.id}, TS: {p.timestamp}, Lat: {p.latitude}, Lon: {p.longitude}, Alt: {p.height}")
            print(f"       Displacements (m): East={p.east_displacement:.4f}, North={p.north_displacement:.4f}, Up={p.up_displacement:.4f}")
            print(f"       Fix: {p.fix_type}, Sats: {p.satellites}, HDOP: {p.hdop}, Volt: {p.battery_voltage}")
finally:
    db.close()
