import asyncio
import json
import random
import websockets
import time

WS_URL = "ws://localhost:8443/ws"

async def send(ws, payload):
    await ws.send(json.dumps(payload))

async def run():
    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL) as ws:
        print("Connected. Streaming simulated SentinelEye data...")
        frame = 0
        while True:
            now = time.time()
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            openness = max(0.05, min(1.0, random.gauss(0.72, 0.18)))
            roll = random.random()
            if roll < 0.18:
                result = "ASLEEP"
                confidence = random.uniform(0.80, 0.97)
            elif roll < 0.45:
                result = "DROWSY"
                confidence = random.uniform(0.65, 0.90)
            else:
                result = "AWAKE"
                confidence = random.uniform(0.85, 0.99)
            await send(ws, {
                "type": "inference",
                "data": {
                    "result": result,
                    "confidence": round(confidence, 3),
                    "openness": round(openness, 3),
                    "timestamp": ts,
                    "frameNumber": frame
                }
            })
            if result != "AWAKE":
                level = 3 if result == "ASLEEP" else 2
                await send(ws, {
                    "type": "alert",
                    "data": {
                        "type": "DROWSINESS_HIGH" if result == "ASLEEP" else "DROWSINESS_LOW",
                        "level": level,
                        "message": f"{result} - confidence {confidence:.0%}",
                        "timestamp": ts,
                        "deviceId": "S1-ESP32S3"
                    }
                })
            await send(ws, {
                "type": "status",
                "data": {
                    "deviceId": "S1-ESP32S3",
                    "firmwareVersion": "1.0.0",
                    "state": "ACTIVE",
                    "framesProcessed": frame + 1,
                    "inferenceCount": frame + 1,
                    "drowsyFrames": sum(1 for _ in range(frame + 1) if random.random() < 0.35),
                    "avgInferenceUs": round(random.uniform(7.0, 9.5), 1),
                    "cpuFreqMhz": 240,
                    "batteryVoltage": round(random.uniform(3.55, 3.85), 3),
                    "batterySoc": round(random.uniform(65, 92), 1),
                    "batteryCharging": random.random() < 0.15
                }
            })
            frame += 1
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Stopped.")
