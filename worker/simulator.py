import time
import json
import math
import random
import paho.mqtt.client as mqtt

# Configuration
MQTT_HOST = "mosquitto"
MQTT_PORT = 1883
MQTT_USER = "worker"
MQTT_PASSWORD = "workerpass"

# Default Rover coordinates (Reference locations)
ROVERS = {
    "rover-01": {
        "lat": -6.789123456, "lon": 107.123456789, "alt": 1250.415,
        "fix_type": "RTK_FIX", "sats": 15, "hdop": 0.6, "volt": 12.2,
        "behavior": "safe"
    },
    "rover-02": {
        "lat": -6.788412330, "lon": 107.126891004, "alt": 1243.882,
        "fix_type": "RTK_FIX", "sats": 14, "hdop": 0.7, "volt": 12.1,
        "behavior": "moving_danger"
    },
    "rover-03": {
        "lat": -6.786901221, "lon": 107.124773100, "alt": 1261.204,
        "fix_type": "RTK_FLOAT", "sats": 7, "hdop": 1.8, "volt": 12.0,
        "behavior": "bad_quality"
    },
    "rover-04": {
        "lat": -6.791004778, "lon": 107.125410990, "alt": 1218.760,
        "fix_type": "RTK_FIX", "sats": 12, "hdop": 0.8, "volt": 11.9,
        "behavior": "safe"
    },
    "rover-05": {
        "lat": -6.790233145, "lon": 107.121880042, "alt": 1232.508,
        "fix_type": "RTK_FIX", "sats": 13, "hdop": 0.7, "volt": 11.2,
        "behavior": "low_battery"
    }
}

def add_displacement(ref_lat, ref_lon, ref_alt, de_meters, dn_meters, du_meters):
    # Constants for simple WGS84 approximation
    lat_deg_len = 111132.954
    lon_deg_len = lat_deg_len * math.cos(math.radians(ref_lat))
    
    lat = ref_lat + (dn_meters / lat_deg_len)
    lon = ref_lon + (de_meters / lon_deg_len)
    alt = ref_alt + du_meters
    return lat, lon, alt

def main():
    print("Starting GNSS Telemetry Simulator...")
    client = mqtt.Client(client_id="gnss_simulator")
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    
    # Connect to mosquitto
    connected = False
    for i in range(10):
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            connected = True
            print("Connected to Mosquitto Broker!")
            break
        except Exception as e:
            print(f"Waiting for mosquitto... ({i+1}/10) - Error: {e}")
            time.sleep(2)
            
    if not connected:
        print("Failed to connect to broker. Exiting.")
        return

    step = 0
    while True:
        step += 1
        print(f"\n--- Simulation Step {step} ---")
        
        for rover_id, data in ROVERS.items():
            # Calculate displacements in meters
            de, dn, du = 0.0, 0.0, 0.0
            
            # Simulate different scenarios based on behavior type
            if data["behavior"] == "safe":
                # Very small random jitter (0 to 5 mm)
                de = random.uniform(-0.003, 0.003)
                dn = random.uniform(-0.003, 0.003)
                du = random.uniform(-0.005, 0.005)
            elif data["behavior"] == "moving_danger":
                # Gradually increase displacement from 42mm to 55mm over steps
                current_disp_mm = 42.0 + min(15.0, step * 0.8) # starts at 42.8, goes to 55mm
                # Project displacement mostly along East axis with small random perturbations
                de = current_disp_mm / 1000.0
                dn = random.uniform(-0.002, 0.002)
                du = random.uniform(-0.002, 0.002)
            elif data["behavior"] == "bad_quality":
                # Static position, but poor fix characteristics
                de = 0.0084
                dn = -0.0051
                du = 0.0019
            elif data["behavior"] == "low_battery":
                # Jitter + decreasing battery voltage
                de = 0.0180 + random.uniform(-0.002, 0.002)
                dn = 0.0160 + random.uniform(-0.002, 0.002)
                du = -0.0041 + random.uniform(-0.002, 0.002)
                # voltage slowly decays down to 10.5V
                data["volt"] = max(10.5, data["volt"] - 0.01)

            # Apply displacement to reference LLA to get final simulated LLA
            lat, lon, alt = add_displacement(data["lat"], data["lon"], data["alt"], de, dn, du)
            
            # Construct MQTT payload
            payload = {
                "latitude": lat,
                "longitude": lon,
                "altitude_m": alt,
                "battery_voltage": round(data["volt"], 2),
                "satellites_active": data["sats"],
                "hdop": data["hdop"],
                "fix_type": data["fix_type"]
            }
            
            topic = f"sigap/{rover_id}/telemetry"
            payload_str = json.dumps(payload)
            client.publish(topic, payload_str)
            print(f"Published to {topic}: {payload_str}")
            
        time.sleep(5)

if __name__ == "__main__":
    main()
