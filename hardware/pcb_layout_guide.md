# SentinelEye PCB Layout Guide
# 4-Layer Stackup: Signal / GND / 3V3 / Signal
# Board Size: 45mm x 35mm

Layer 1: Top - Signal (35um copper)
Layer 2: Inner1 - Ground Plane (35um copper, solid)
Layer 3: Inner2 - 3V3 Power Plane (35um copper, solid)
Layer 4: Bottom - Signal (35um copper)

## Critical Routing Notes

### Power Rails
- USB VBUS (5V) enters via J1, polyfuse F1 (500mA) to MCP73831 VDD
- MCP73831 BAT drives L1 (10uH boost) to 5V rail
- 5V rail feeds NCP1117-3.3 IN pin
- 3V3 OUT is distributed on Layer 3 solid plane
- Keep 3V3 trace width >= 15mil for power segments

### Camera MIPI
- Route MIPI DP/DN as 100ohm differential pairs
- Pair width 6mil, spacing 6mil
- Keep diff pair length matched within 0.5mm
- Keep diff pairs away from switching regulators (keep 15mil clearance)
- Length of diff pair <= 100mm total
- Via stubs on MIPI should be kept < 5mil (back-drill recommended)

### I2S Audio
- BCLK, LRC, DIN are 50ohm single-ended traces
- Length match: BCLK and LRC within 0.5mm
- Route I2S away from camera MIPI (keep 20mil clearance)
- Keep audio traces < 80mm total

### Haptic
- EN and PWM lines are GPIO, max 10MHz
- Keep within 50mm
- Add 4.7k pull-up on SDA, SCL (I2C)

### ESP32-S3 Antenna
- ANT1 (2.4GHz) must be on bottom layer
- Keep ground pour 2mm away from antenna keepout zone
- No copper or components in 5mm radius of antenna
- Route antenna trace on bottom layer, 30mil width, solid
- Keepout zone: 10mm x 10mm oval centered on ANT1

### Crystal
- Y1 (40MHz): 22pF caps C3, C4 to GND
  Route caps symmetrically, keep stubs short (<3mm)
  Keepaway zone 10mm radius from switching nodes
- Y2 (32.768kHz): Load caps 22pF
  Same rules as Y1

### USB
- USB D+/D- are 90ohm differential
- Route on top layer, 5mil width, 6mil spacing
- Series 22ohm resistors near J1
- D3 (ESD5V0D3) placement within 5mm of J1 pins
- 3mil clearance from USB D+/D- to any other net

### LED Indicators
- D1 (Green Status) on GPIO11, 330ohm resistor R4
- D2 (Red Alert) on GPIO12, 330ohm resistor R3
- Place LEDs near PCB edge for visibility
- Use 0603 size, spaced 5mm apart

### General Guidelines
- All power traces >= 15mil width
- Signal traces >= 6mil width
- Minimum via drill: 0.3mm
- Use 0.2mm annular ring on vias
- Keep all switching traces <= 20mm from camera
- Solid ground plane on Layer 2 - no splits
- All components on top side for hand-solder prototyping
- Provide 0.5mm soldermask expansion on all pads
- Silkscreen text height >= 0.2mm

## Placement Guide

Top Layer Placement (priority order):
1. ESP32-S3-WROOM-1 (U1): center, antenna keepout zone
2. OV5647 Camera (U2): top edge, MIPI route straight down
3. MAX98357A (U3): bottom left, near speaker connector
4. DRV2605 (U4): bottom right, near haptic connector
5. J1 (USB-C): top center edge
6. J2 (Camera FFC): top edge, near camera
7. J3 (Speaker): bottom left edge
8. J4 (Haptic): bottom right edge
9. J5 (Battery): bottom left
10. Crystal Y1: near U1, within 5mm
11. Crystal Y2: near U1, within 5mm

Bottom Layer:
1. ANT1 (antenna): bottom left, far from camera
2. Ground fill everywhere else

## Thermal
- L1 (10uH inductor) can get warm: place with 5mm clearance to thermal-sensitive components
- U7 (NCP1117) can get warm: add copper pour, 10mm x 10mm recommended
- Thermal via array under U7: 10 vias, 0.3mm drill, 0.6mm pad

## Assembly
- All components are top-side for prototype
- Use leaded solder paste: Sn63Pb37
- Reflow profile: 240C peak, 60s dwell
- Use 0.3mm stencil thickness
- Recommended paste: KOKI S3G64-M400
