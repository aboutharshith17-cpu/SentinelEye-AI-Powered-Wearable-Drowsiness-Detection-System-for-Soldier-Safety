import time
import random
import requests
import json

BASE = "http://localhost:8443"
CLASSES = ["Awake", "Drowsy", "Asleep"]

def post(path, payload):
    try:
        r = requests.post(f"{BASE}{path}", json=payload, timeout=2)
        print(f"POST {path} -> {r.status_code}")
        return r
    except Exception as e:
        print(f"POST {path} failed: {e}")
        return None

def main():
    print("SentinelEye live demo simulator")
    print(f"Dashboard: {BASE}")
    print("Press Ctrl+C to stop\n")
    frame = 0
    drowsy_frames = 0
    while True:
        now = time.time()
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        roll = random.random()
        if roll < 0.18:
            result = "Asleep"
            confidence = random.uniform(0.80, 0.97)
        elif roll < 0.45:
            result = "Drowsy"
            confidence = random.uniform(0.65, 0.90)
        else:
            result = "Awake"
            confidence = random.uniform(0.85, 0.99)
        openness = max(0.05, min(1.0, random.gauss(0.72, 0.18)))
        post("/api/inference", {
            "result": result,
            "confidence": round(confidence, 3),
            "openness": round(openness, 3),
            "timestamp": ts
        })
        if result != "Awake":
            level = 3 if result == "Asleep" else 2
            post("/api/alert", {
                "type": "DROWSINESS_HIGH" if result == "Asleep" else "DROWSINESS_LOW",
                "level": level,
                "message": f"{result.upper()} - confidence {confidence:.0%}",
                "timestamp": ts,
                "deviceId": "S1-ESP32S3"
            })
            drowsy_frames += 1
            post("/api/device/status", {
                "device_id": "S1-ESP32S3",
                "firmware_version": "1.0.0",
                "state": "ACTIVE",
                "frames_processed": frame + 1,
                "inference_count": frame + 1,
                "drowsy_frames": drowsy_frames,
                "avg_inference_us": round(random.uniform(7.0, 9.5), 1),
                "cpu_freq_mhz": 240,
                "battery_voltage": round(random.uniform(3.55, 3.85), 3),
                "battery_soc": round(random.uniform(65, 92), 1),
                "battery_charging": random.random() < 0.15
            })
        frame += 1
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped.")
