import subprocess

# Lat/Lon/Alt close to rover-01 reference coordinates:
# Ref: Lat = -6.789123456, Lon = 107.123456789, Height = 1250.415
# Simulated minor displacement: North = 5mm, East = 10mm, Vertical = -2mm
payload = '{"latitude":-6.789123411, "longitude":107.123456880, "altitude_m":1250.413, "battery_voltage":12.4, "satellites_active":16, "hdop":0.5, "fix_type":"RTK_FIX"}'

subprocess.run([
    'docker', 'exec', '-i', 'gnss_mosquitto', 
    'mosquitto_pub', 
    '-u', 'worker', 
    '-P', 'workerpass', 
    '-t', 'sigap/rover-01/telemetry', 
    '-m', payload
])
print("Telemetry published successfully!")
