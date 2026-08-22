import subprocess

payload = '{"latitude":-6.791004778, "longitude":107.125410990, "altitude_m":1218.760, "battery_voltage":12.2, "satellites_active":15, "hdop":0.6, "fix_type":"RTK_FIX"}'

subprocess.run([
    'docker', 'exec', '-i', 'gnss_mosquitto', 
    'mosquitto_pub', 
    '-u', 'worker', 
    '-P', 'workerpass', 
    '-t', 'sigap/rover-04/telemetry', 
    '-m', payload
])
print("Telemetry published successfully!")
