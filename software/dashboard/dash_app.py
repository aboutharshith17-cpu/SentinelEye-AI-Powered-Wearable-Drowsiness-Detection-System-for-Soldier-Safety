"""
dash_app.py
SentinelEye Web Dashboard - Real-time monitoring and analytics
FastAPI + WebSocket + Plotly for live visualization
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from collections import deque

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import plotly.graph_objs as go
import plotly.utils
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentinelseye.dashboard")

# FastAPI app
app = FastAPI(
    title="SentinelEye Dashboard",
    description="AI-Powered Wearable Drowsiness Detection System - Real-time Monitoring",
    version="1.0.0"
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.inference_history: deque = deque(maxlen=1000)
        self.alert_history: deque = deque(maxlen=500)
        self.device_stats = {
            'device_id': 'S1-ESP32S3',
            'firmware_version': '1.0.0',
            'state': 'ACTIVE',
            'frames_processed': 0,
            'inference_count': 0,
            'drowsy_frames': 0,
            'avg_inference_us': 0.0,
            'cpu_freq_mhz': 240,
            'battery_voltage': 3700.0,
            'battery_soc': 85.0,
            'battery_charging': False
        }

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Dashboard client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Dashboard client disconnected. Total: {len(self.active_connections)}")

    def _coerce_status(self, data: dict) -> dict:
        coerced = dict(manager.device_stats)
        mapping = {
            "deviceId": "device_id",
            "firmwareVersion": "firmware_version",
            "framesProcessed": "frames_processed",
            "inferenceCount": "inference_count",
            "drowsyFrames": "drowsy_frames",
            "avgInferenceUs": "avg_inference_us",
            "cpuFreqMhz": "cpu_freq_mhz",
            "batteryVoltage": "battery_voltage",
            "batterySoc": "battery_soc",
            "batteryCharging": "battery_charging",
        }
        for src, dst in mapping.items():
            if src in data:
                coerced[dst] = data[src]
        coerced.update({k: v for k, v in data.items() if k not in mapping})
        return coerced

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    def add_inference(self, result: str, confidence: float, openness: float):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'result': result,
            'confidence': confidence,
            'openness': openness
        }
        self.inference_history.append(entry)
        self.device_stats['inference_count'] = int(self.device_stats.get('inference_count', 0)) + 1
        self.device_stats['frames_processed'] = int(self.device_stats.get('frames_processed', 0)) + 1
        if result in ('DROWSY', 'ASLEEP'):
            self.device_stats['drowsy_frames'] = int(self.device_stats.get('drowsy_frames', 0)) + 1

    def add_alert(self, alert_type: str, level: int, message: str):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'level': level,
            'message': message
        }
        self.alert_history.append(entry)

manager = ConnectionManager()

# ==================== PYDANTIC MODELS ====================

class InferenceResult(BaseModel):
    result: str
    confidence: float
    openness: float
    timestamp: str

class AlertMessage(BaseModel):
    type: str
    level: int
    message: str
    timestamp: str

class DeviceStatus(BaseModel):
    device_id: str
    firmware_version: str
    state: str
    frames_processed: int
    inference_count: int
    drowsy_frames: int
    avg_inference_us: float
    cpu_freq_mhz: int
    battery_voltage: float
    battery_soc: float
    battery_charging: bool

    model_config = {"extra": "allow"}

# ==================== REST ENDPOINTS ====================

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve main dashboard HTML"""
    html_path = Path(__file__).parent / "dashboard" / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return generate_dashboard_html()

@app.get("/api/status", response_model=DeviceStatus)
async def get_device_status():
    """Get current device status"""
    return DeviceStatus(**manager.device_stats)

@app.get("/api/inference/history")
async def get_inference_history(limit: int = 100):
    """Get recent inference history"""
    history = list(manager.inference_history)[-limit:]
    return JSONResponse(content=history)

@app.get("/api/alerts/history")
async def get_alert_history(limit: int = 100):
    """Get recent alert history"""
    history = list(manager.alert_history)[-limit:]
    return JSONResponse(content=history)

@app.get("/api/metrics/summary")
async def get_metrics_summary():
    """Get aggregated metrics summary"""
    if not manager.inference_history:
        return JSONResponse(content={
            'total_inferences': 0,
            'drowsy_count': 0,
            'awake_count': 0,
            'asleep_count': 0,
            'drowsiness_rate': 0.0,
            'avg_confidence': 0.0,
            'avg_openness': 0.0,
            'avg_inference_us': 0.0
        })

    inferences = list(manager.inference_history)
    drowsy_count = sum(1 for i in inferences if i['result'] in ['DROWSY', 'ASLEEP'])
    avg_confidence = np.mean([i['confidence'] for i in inferences])
    avg_openness = np.mean([i['openness'] for i in inferences])

    return JSONResponse(content={
        'total_inferences': len(inferences),
        'drowsy_count': drowsy_count,
        'awake_count': len(inferences) - drowsy_count,
        'asleep_count': sum(1 for i in inferences if i['result'] == 'ASLEEP'),
        'drowsiness_rate': (drowsy_count / len(inferences)) * 100.0,
        'avg_confidence': float(avg_confidence),
        'avg_openness': float(avg_openness),
        'avg_inference_us': float(manager.device_stats['avg_inference_us'])
    })

@app.post("/api/inference")
async def post_inference_result(result: InferenceResult):
    """Receive inference result from device"""
    manager.add_inference(result.result, result.confidence, result.openness)
    await manager.broadcast({
        'type': 'inference',
        'data': result.dict()
    })
    return {"status": "ok"}

@app.post("/api/alert")
async def post_alert(alert: AlertMessage):
    """Receive alert from device"""
    manager.add_alert(alert.type, alert.level, alert.message)
    await manager.broadcast({
        'type': 'alert',
        'data': alert.dict()
    })
    return {"status": "ok"}

@app.post("/api/device/status")
async def update_device_status(status: DeviceStatus):
    """Update device status"""
    merged = dict(manager.device_stats)
    merged.update(status.model_dump())
    manager.device_stats = merged
    await manager.broadcast({
        'type': 'status',
        'data': manager.device_stats
    })
    return {"status": "ok"}

# ==================== WEBSOCKET ENDPOINT ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get('type') == 'inference':
                result = InferenceResult(**data['data'])
                manager.add_inference(result.result, result.confidence, result.openness)
            elif data.get('type') == 'alert':
                alert = AlertMessage(**data['data'])
                manager.add_alert(alert.type, alert.level, alert.message)
            elif data.get('type') == 'status':
                manager.device_stats = data['data']
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# ==================== DASHBOARD HTML ====================

def generate_dashboard_html():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SentinelEye Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #0a0e1a;
            color: #e0e6ed;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #1a2332, #2d3748);
            border-radius: 12px;
            border: 1px solid #3b5998;
        }
        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(45deg, #4a9eff, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: #151d2e;
            border: 1px solid #2d3748;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s;
        }
        .card:hover {
            border-color: #4a9eff;
            transform: translateY(-2px);
        }
        .card-title {
            font-size: 1.1em;
            color: #8b9fc5;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            background: linear-gradient(45deg, #4a9eff, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .metric-unit {
            font-size: 1em;
            color: #8b9fc5;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        .status-online { background: #00ff88; }
        .status-warning { background: #ffaa00; }
        .status-critical { background: #ff4444; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .alert-log {
            max-height: 400px;
            overflow-y: auto;
            background: #0a0e1a;
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.9em;
        }
        .alert-entry {
            padding: 8px;
            margin: 4px 0;
            border-radius: 4px;
            border-left: 3px solid #4a9eff;
        }
        .alert-critical { border-left-color: #ff4444; background: #2d1515; }
        .alert-warning { border-left-color: #ffaa00; background: #2d2515; }
        .alert-info { border-left-color: #4a9eff; background: #15202d; }
        #inferenceChart, #alertChart, #opennessChart {
            height: 350px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>SentinelEye Command Center</h1>
        <p>AI-Powered Wearable Drowsiness Detection System</p>
        <p><span class="status-indicator status-online"></span>System Online | Device: S1-ESP32S3</p>
    </div>

    <div class="grid">
        <div class="card">
            <div class="card-title">Total Inferences</div>
            <div class="metric-value" id="totalInferences">0</div>
            <div class="metric-unit">CNN predictions</div>
        </div>
        <div class="card">
            <div class="card-title">Drowsy Frames</div>
            <div class="metric-value" id="drowsyFrames" style="color: #ff6b6b;">0</div>
            <div class="metric-unit">Fatigue events detected</div>
        </div>
        <div class="card">
            <div class="card-title">Avg Inference Time</div>
            <div class="metric-value" id="avgInference">0.0</div>
            <div class="metric-unit">microseconds</div>
        </div>
        <div class="card">
            <div class="card-title">Battery SOC</div>
            <div class="metric-value" id="batterySOC">85%</div>
            <div class="metric-unit">LiPo 2000mAh</div>
        </div>
        <div class="card">
            <div class="card-title">Battery Voltage</div>
            <div class="metric-value" id="batteryVoltage">3.7V</div>
            <div class="metric-unit">Nominal: 3.7V</div>
        </div>
        <div class="card">
            <div class="card-title">CPU Frequency</div>
            <div class="metric-value" id="cpuFreq">240</div>
            <div class="metric-unit">MHz</div>
        </div>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <div class="card-title">Inference Timeline</div>
        <div id="inferenceChart"></div>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <div class="card-title">Eye Openness Trend</div>
        <div id="opennessChart"></div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="card-title">Drowsiness Rate</div>
            <div id="drowsinessRate" style="font-size: 2em; color: #ffaa00;">0%</div>
            <div class="metric-unit">Last 100 frames</div>
        </div>
        <div class="card">
            <div class="card-title">Confidence</div>
            <div id="avgConfidence" style="font-size: 2em; color: #00d4ff;">0%</div>
            <div class="metric-unit">Model confidence</div>
        </div>
    </div>

    <div class="card">
        <div class="card-title">Alert Log</div>
        <div class="alert-log" id="alertLog">
            <div class="alert-entry alert-info">[SYSTEM] Dashboard initialized</div>
        </div>
    </div>

    <script>
        // WebSocket connection
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const inferenceHistory = [];
        const opennessHistory = [];

        function addAlert(type, level, message) {
            const alertLog = document.getElementById('alertLog');
            const entry = document.createElement('div');
            const time = new Date().toLocaleTimeString();

            let cssClass = 'alert-info';
            if (level === 3) cssClass = 'alert-critical';
            else if (level === 2) cssClass = 'alert-warning';

            entry.className = `alert-entry ${cssClass}`;
            entry.innerHTML = `[${time}] <strong>${type}</strong>: ${message}`;
            alertLog.insertBefore(entry, alertLog.firstChild);
        }

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === 'inference') {
                const data = msg.data;
                inferenceHistory.push({
                    time: new Date(data.timestamp),
                    result: data.result,
                    confidence: data.confidence
                });
                opennessHistory.push({
                    time: new Date(data.timestamp),
                    openness: data.openness
                });

                if (inferenceHistory.length > 100) inferenceHistory.shift();
                if (opennessHistory.length > 100) opennessHistory.shift();
            } else if (msg.type === 'alert') {
                addAlert(msg.data.type, msg.data.level, msg.data.message);
            } else if (msg.type === 'status') {
                const s = msg.data;
                document.getElementById('totalInferences').textContent = s.inference_count;
                document.getElementById('drowsyFrames').textContent = s.drowsy_frames;
                document.getElementById('avgInference').textContent = s.avg_inference_us.toFixed(1);
                document.getElementById('batterySOC').textContent = s.battery_soc.toFixed(0) + '%';
                document.getElementById('batteryVoltage').textContent = (s.battery_voltage / 1000).toFixed(1) + 'V';
                document.getElementById('cpuFreq').textContent = s.cpu_freq_mhz;
            }
        };

        ws.onclose = () => {
            addAlert('SYSTEM', 1, 'WebSocket disconnected - retrying...');
            setTimeout(() => location.reload(), 3000);
        };

        ws.onerror = () => {
            addAlert('SYSTEM', 1, 'WebSocket error');
        };

        // Generate initial charts
        function initCharts() {
            const layout = {
                paper_bgcolor: '#151d2e',
                plot_bgcolor: '#0a0e1a',
                font: { color: '#e0e6ed' },
                xaxis: { gridcolor: '#2d3748', title: 'Time' },
                yaxis: { gridcolor: '#2d3748' },
                margin: { l: 50, r: 20, t: 30, b: 50 }
            };

            const inferenceData = [{
                x: inferenceHistory.map(h => h.time),
                y: inferenceHistory.map(h => h.confidence),
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Confidence',
                line: { color: '#4a9eff', width: 2 }
            }];

            Plotly.newPlot('inferenceChart', inferenceData, layout, {displayModeBar: false});

            const opennessData = [{
                x: opennessHistory.map(h => h.time),
                y: opennessHistory.map(h => h.openness),
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Eye Openness',
                line: { color: '#00d4ff', width: 2 },
                fill: 'tozeroy'
            }];

            Plotly.newPlot('opennessChart', opennessData, layout, {displayModeBar: false});
        }

        initCharts();
        setInterval(initCharts, 5000);
    </script>
</body>
</html>
"""

# ==================== MAIN ====================

if __name__ == "__main__":
    print("="*60)
    print("SentinelEye Dashboard Server")
    print("="*60)
    print("Starting dashboard at http://0.0.0.0:8443")
    print("WebSocket endpoint: ws://0.0.0.0:8443/ws")

    uvicorn.run(
        "dash_app:app",
        host="0.0.0.0",
        port=8443,
        reload=True,
        log_level="info"
    )
