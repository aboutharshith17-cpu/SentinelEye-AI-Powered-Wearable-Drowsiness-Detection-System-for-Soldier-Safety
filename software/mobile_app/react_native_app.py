"""
react_native_app.py
SentinelEye React Native Mobile App
Cross-platform (iOS/Android) mobile interface for soldier monitoring
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

# Simulated React Native structure for documentation
class ReactNativeApp:
    """
    SentinelEye Mobile App
    Technologies: React Native + Expo + TypeScript
    Features: Real-time alerts, biometric monitoring, map view, device config
    """

    def __init__(self):
        self.state = {
            'isConnected': False,
            'deviceId': 'S1-ESP32S3',
            'batteryLevel': 85,
            'currentStatus': 'AWAKE',
            'alerts': deque(maxlen=50),
            'location': {'lat': 0.0, 'lon': 0.0, 'accuracy': 0.0},
            'soldierId': 'SOLDIER-001',
            'unit': 'ALPHA-1',
            'missionTime': '00:00:00'
        }

class AppState:
    """Application state management"""
    def __init__(self):
        self.connectionStatus = 'disconnected'
        self.currentUser = {
            'id': 'SOLDIER-001',
            'name': 'John Doe',
            'rank': 'Sergeant',
            'unit': 'ALPHA-1',
            'bloodType': 'O+',
            'medicalConditions': 'None'
        }
        self.activeAlerts = 0
        self.drowsinessLevel = 0.0
        self.eyeOpenness = 1.0
        self.batteryLevel = 85
        self.location = {'lat': 0.0, 'lon': 0.0}
        self.heartRate = 72
        self.temperature = 98.6

class AlertManager:
    """Manage incoming alerts from device"""
    def __init__(self):
        self.alerts: List[Dict] = []
        self.alertHistory: deque = deque(maxlen=100)

    def add_alert(self, alert_type: str, level: int, message: str,
                  soldier_id: str, location: Dict):
        alert = {
            'id': f"ALT-{int(time.time()*1000)}",
            'type': alert_type,
            'level': level,
            'message': message,
            'soldier_id': soldier_id,
            'location': location,
            'timestamp': datetime.now().isoformat(),
            'acknowledged': False,
            'priority': self._get_priority(level)
        }
        self.alerts.append(alert)
        self.alertHistory.append(alert)

        # Push notification for high-priority alerts
        if level >= 2:
            self._send_push_notification(alert)

        return alert

    def _get_priority(self, level: int) -> str:
        if level >= 3: return 'CRITICAL'
        if level == 2: return 'HIGH'
        return 'MEDIUM'

    def _send_push_notification(self, alert: Dict):
        """Send push notification via Firebase"""
        pass

class DashboardScreen:
    """Main dashboard screen"""
    def __init__(self):
        self.components = {
            'header': {
                'title': 'SentinelEye',
                'subtitle': 'Drowsiness Monitor',
                'connectionStatus': True,
                'batteryLevel': 85
            },
            'statusCard': {
                'status': 'AWAKE',
                'confidence': 0.97,
                'eyeOpenness': 0.89,
                'lastUpdate': datetime.now().isoformat()
            },
            'metricsGrid': {
                'inferences': 1547,
                'drowsyFrames': 23,
                'avgInference': 8.2,
                'cpuTemp': 42
            },
            'mapView': {
                'center': {'lat': 0.0, 'lon': 0.0},
                'markers': []
            }
        }

class AlertsScreen:
    """Alerts history screen"""
    def __init__(self):
        self.alertFilters = {
            'all': True,
            'critical': True,
            'warning': True,
            'info': True
        }
        self.alertManager = AlertManager()

class SettingsScreen:
    """Device settings screen"""
    def __init__(self):
        self.settings = {
            'alertThreshold': 0.55,
            'audioEnabled': True,
            'hapticEnabled': True,
            'vibrationPattern': 'strong',
            'alertCooldown': 3.0,
            'cameraFPS': 15,
            'inferenceInterval': 1.0,
            'lowPowerMode': False,
            'autoSleepTimeout': 3600
        }

# ==================== TYPESCRIPT INTERFACES ====================

typescript_interfaces = """
// types/sentinelseye.ts

export interface Soldier {
  id: string;
  name: string;
  rank: string;
  unit: string;
  bloodType: string;
  medicalConditions: string;
  deviceId: string;
}

export interface DeviceStatus {
  deviceId: string;
  firmwareVersion: string;
  state: 'INIT' | 'ACTIVE' | 'LOW_POWER' | 'DEEP_SLEEP' | 'ERROR';
  battery: {
    voltage: number;
    current: number;
    soc: number;
    charging: boolean;
  };
  inference: {
    total: number;
    count: number;
    avgTimeUs: number;
    drowsyFrames: number;
  };
  network: {
    wifiConnected: boolean;
    bleActive: boolean;
  };
  lastUpdate: string;
}

export interface InferenceResult {
  result: 'AWAKE' | 'DROWSY' | 'ASLEEP';
  confidence: number;
  eyeOpenness: number;
  timestamp: string;
  frameNumber: number;
}

export interface Alert {
  id: string;
  type: string;
  level: 1 | 2 | 3;
  message: string;
  soldierId: string;
  location: { lat: number; lon: number };
  timestamp: string;
  acknowledged: boolean;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

export interface MapMarker {
  id: string;
  soldierId: string;
  location: { lat: number; lon: number };
  status: string;
  batteryLevel: number;
  alertLevel: number;
}

export interface WebSocketMessage {
  type: 'inference' | 'alert' | 'status' | 'location';
  data: any;
}

export interface AppSettings {
  alertThreshold: number;
  audioEnabled: boolean;
  hapticEnabled: boolean;
  vibrationPattern: string;
  alertCooldown: number;
  cameraFPS: number;
  inferenceInterval: number;
  lowPowerMode: boolean;
  autoSleepTimeout: number;
}
"""

# ==================== MAIN APP COMPONENT ====================

react_native_app = """
// App.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { WebSocket } from 'react-native-native';
import { Alert, Vibration, Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

import DashboardScreen from './src/screens/DashboardScreen';
import AlertsScreen from './src/screens/AlertsScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import MapScreen from './src/screens/MapScreen';
import BiometricScreen from './src/screens/BiometricScreen';

import { DeviceStatus, InferenceResult, Alert, AppSettings } from './src/types/sentinelseye';
import { WebSocketService } from './src/services/websocket';
import { NotificationService } from './src/services/notifications';
import { LocationService } from './src/services/location';

const Stack = createStackNavigator();

export default function App() {
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatus | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [settings, setSettings] = useState<AppSettings>({
    alertThreshold: 0.55,
    audioEnabled: true,
    hapticEnabled: true,
    vibrationPattern: 'strong',
    alertCooldown: 3.0,
    cameraFPS: 15,
    inferenceInterval: 1.0,
    lowPowerMode: false,
    autoSleepTimeout: 3600
  });

  // Initialize services
  useEffect(() => {
    const initServices = async () => {
      // Load saved settings
      const savedSettings = await AsyncStorage.getItem('sentinelseye_settings');
      if (savedSettings) {
        setSettings(JSON.parse(savedSettings));
      }

      // Initialize WebSocket
      const ws = WebSocketService.connect('ws://192.168.4.1:8443/ws');
      ws.onMessage(handleIncomingMessage);
      ws.onConnect(() => setIsConnected(true));
      ws.onDisconnect(() => setIsConnected(false));

      // Initialize location tracking
      await LocationService.startTracking();

      // Request notification permissions
      await NotificationService.requestPermissions();

      return () => ws.disconnect();
    };

    initServices();
  }, []);

  const handleIncomingMessage = useCallback((message) => {
    switch (message.type) {
      case 'status':
        setDeviceStatus(message.data);
        break;
      case 'inference':
        const inference = message.data as InferenceResult;
        if (inference.result !== 'AWAKE') {
          triggerAlert(inference);
        }
        break;
      case 'alert':
        const alert = message.data;
        setAlerts(prev => [alert, ...prev].slice(0, 100));
        showAlertNotification(alert);
        break;
    }
  }, [settings]);

  const triggerAlert = (inference: InferenceResult) => {
    if (settings.audioEnabled) {
      // Play audio alert
      AudioService.playAlert(inference.result);
    }
    if (settings.hapticEnabled) {
      Vibration.vibrate(
        inference.result === 'ASLEEP' ? [500, 200, 500] : [300, 200, 300],
        -1
      );
    }
  };

  const showAlertNotification = (alert: Alert) => {
    if (alert.level >= 2) {
      Alert.alert(
        `⚠️ ${alert.priority} ALERT`,
        alert.message,
        [
          { text: 'Acknowledge', onPress: () => acknowledgeAlert(alert.id) },
          { text: 'View Details', onPress: () => {} }
        ],
        { cancelable: false }
      );

      NotificationService.showPushNotification(
        alert.type,
        alert.message,
        { priority: 'high', sound: 'alarm.wav' }
      );
    }
  };

  const acknowledgeAlert = async (alertId: string) => {
    const updatedAlerts = alerts.map(a =>
      a.id === alertId ? { ...a, acknowledged: true } : a
    );
    setAlerts(updatedAlerts);
    await AsyncStorage.setItem('sentinelseye_alerts', JSON.stringify(updatedAlerts));
  };

  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Dashboard">
        <Stack.Screen name="Dashboard">
          {(props) => (
            <DashboardScreen
              {...props}
              deviceStatus={deviceStatus}
              isConnected={isConnected}
            />
          )}
        </Stack.Screen>
        <Stack.Screen name="Alerts" options={{ title: 'Alert History' }}>
          {(props) => <AlertsScreen {...props} alerts={alerts} />}
        </Stack.Screen>
        <Stack.Screen name="Map" options={{ title: 'Unit Positions' }}>
          {(props) => <MapScreen {...props} />}
        </Stack.Screen>
        <Stack.Screen name="Biometrics" options={{ title: 'Health Monitor' }}>
          {(props) => <BiometricScreen {...props} />}
        </Stack.Screen>
        <Stack.Screen name="Settings">
          {(props) => (
            <SettingsScreen
              {...props}
              settings={settings}
              onSettingsChange={setSettings}
            />
          )}
        </Stack.Screen>
      </Stack.Navigator>
    </NavigationContainer>
  );
}
"""

# ==================== WEBSOCKET SERVICE ====================

websocket_service = """
// src/services/websocket.ts
import { DeviceStatus, InferenceResult, Alert } from '../types/sentinelseye';

class WebSocketService {
  private ws: WebSocket | null = null;
  private messageHandlers: ((msg: any) => void)[] = [];
  private connectHandlers: (() => void)[] = [];
  private disconnectHandlers: (() => void)[] = [];

  connect(url: string): this {
    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('WebSocket connected to', url);
        this.connectHandlers.forEach(h => h());
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.messageHandlers.forEach(h => h(msg));
        } catch (e) {
          console.error('Failed to parse message:', e);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.disconnectHandlers.forEach(h => h());
        // Auto-reconnect after 3s
        setTimeout(() => this.connect(url), 3000);
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (e) {
      console.error('WebSocket connection failed:', e);
    }

    return this;
  }

  onMessage(handler: (msg: any) => void) {
    this.messageHandlers.push(handler);
  }

  onConnect(handler: () => void) {
    this.connectHandlers.push(handler);
  }

  onDisconnect(handler: () => void) {
    this.disconnectHandlers.push(handler);
  }

  send(type: string, data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data }));
    }
  }

  disconnect() {
    this.ws?.close();
    this.ws = null;
  }
}

export const WebSocketService = new WebSocketService();
"""

print("="*60)
print("SentinelEye React Native Mobile App")
print("="*60)
print("Technologies: React Native + Expo + TypeScript")
print("Features:")
print("  - Real-time drowsiness monitoring")
print("  - Push notification alerts")
print("  - GPS location tracking")
print("  - Biometric sensor integration")
print("  - Multi-soldier command view")
print("  - Offline mode with sync")
print("="*60)
print("\nProject structure:")
print("├── App.tsx")
print("├── src/")
print("│   ├── screens/")
print("│   │   ├── DashboardScreen.tsx")
print("│   │   ├── AlertsScreen.tsx")
print("│   │   ├── MapScreen.tsx")
print("│   │   ├── BiometricScreen.tsx")
print("│   │   └── SettingsScreen.tsx")
print("│   ├── services/")
print("│   │   ├── websocket.ts")
print("│   │   ├── notifications.ts")
print("│   │   └── location.ts")
print("│   └── types/sentinelseye.ts")
print("├── package.json")
print("└── app.json")
print("="*60)
