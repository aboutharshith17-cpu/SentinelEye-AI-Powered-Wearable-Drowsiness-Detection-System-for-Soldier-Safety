# SentinelEye Hardware Wiring Guide
## System Wiring Diagram

```
LiPo Battery (BT1: 3.7V 2000mAh)
    |
    +--[J5: JST-PH]-->+----[MCP73831:BAT]----[MCP73831:PROG]--[R5:1k]--+--[GND]
    |               |                                                        |
    |               +----[CW2015:BAT]-------[CW2015:ALRM]--[R6:10k]--[GND]   |
    |                                                                         |
    +----[L1:10uH]----+-----[NCP1117:IN]----[C4:47uF]----+                  |
                        |                                   |                 |
                   [USB-C:VBUS]---[F1:500mA]---+             |                 |
                        |                        |             |                 |
                        +-----[D3:ESD]-----------[NCP1117:IN]                 |
                                                                              |
                                                                  [NCP1117:OUT]---[3V3]------------------------------------------------+
                                                                                   |                                                        |
                                                                           [ESP32:3V3]                                         [OV5647:3V3]
                                                                                   |                                                        |
                                                                           [ESP32:GND]                                         [OV5647:GND]
                                                                                   |                                                        |
                                                                   +-----------+-----------+                                            |
                                                                   |                       |                                            |
                                                               [MAX98357:VDD]         [DRV2605:VDD]                                  |
                                                                   |                       |                                            |
                                                                   +-----------+-----------+                                            |
                                                                               |                                                        |
                                                                           [CW2015:VDD]                                                |
                                                                               |                                                        |
                                                                   +-----------+-----------+                                            |
                                                                   |                       |                                            |
                                                               [I2C_SCL]--[R2:4.7k]--[GND]                                    |
                                                                   |                                                                       |
                                                                   [I2C_SDA]--[R2:4.7k]--[GND]                                    |
                                                                   |                                                                       |
                                                              [DRV2605:SCL]--[ESP32:I2C_SCL]                                     |
                                                              [DRV2605:SDA]--[ESP32:I2C_SDA]--[CW2015:SDA]                      |
                                                              [DRV2605:EN]---[ESP32:GPIO9]--[R3:330]---[3V3]                     |
                                                              [DRV2605:PWM]--[ESP32:GPIO10]                                      |
                                                                   |                                                                       |
                                                              [MAX98357:BCLK]-[ESP32:I2S_BCLK]                                     |
                                                              [MAX98357:LRC]--[ESP32:I2S_LRCLK]                                    |
                                                              [MAX98357:DIN]--[ESP32:I2S_DIN]                                      |
                                                                   |                                                                       |
                                                                   [SP1:+]-----+                                                         |
                                                                   [SP1:-]-----+                                                         |
                                                                   |                                                                       |
                                                              [MOTOR:+]---[DRV2605:OUT1]                                              |
                                                              [MOTOR:-]---[DRV2605:OUT2]                                              |
                                                                   |                                                                       |
                                                              [CAM_DP]-----+                                                          |
                                                              [CAM_DN]-----+                                                          |
                                                                   |                                                                       |
                                                                  [OV5647:MIPI_DP]--[ESP32:CAM_MIPI_DP]                                  |
                                                                  [OV5647:MIPI_DN]--[ESP32:CAM_MIPI_DN]                                  |
                                                                   |                                                                       |
                                                              [ESP32:GPIO11]--[R4:100k]--[GND]                                        |
                                                                   |                                                                       |
                                                              [ESP32:GPIO11]--[D2:Red LED:Anode]---[Cathode]--[GND]                  |
                                                                   |                                                                       |
                                                              [ESP32:GPIO12]--[D1:Green LED:Anode]--[Cathode]--[GND]                 |
                                                                   |                                                                       |
                                                              [ESP32:EN]-----+                                                         |
                                                                                  |                                                         |
                                                                             [SW1:Reset]--[GND]                                           |
                                                                                  |                                                         |
                                                                              [BOOT_MODE]--[J1:IO0]--[R1:10k]--[3V3]                      |
                                                                                  |                                                         |
                                                                             [USB_DP]-----+--[D3]--[J1:D+]                               |
                                                                             [USB_DN]-----+--[D3]--[J1:D-]                               |
                                                                                  |                                                         |
                                                                              [ANT1]----[J6:IPEX]--[ESP32:ANT]                           |
                                                                                  |                                                         |
                                                                              [Y1:40MHz]--[ESP32:XTAL]                                    |
                                                                               |    |                                                     |
                                                                              [C3] [C4]                                                    |
                                                                               |    |                                                     |
                                                                              [GND][GND]                                                   |
```

## Pin Assignments Summary

### ESP32-S3 Pinout
| GPIO | Function | Direction | Net | Component |
|------|----------|-----------|-----|-----------|
| GPIO0 | Boot Mode | Input | BOOT | J1, R1 |
| GPIO9 | Haptic EN | Output | HAPTIC_EN | U4, R3 |
| GPIO10 | Haptic PWM | Output | HAPTIC_PWM | U4 |
| GPIO11 | Alert LED | Output | ALERT_LED | D2, R4 |
| GPIO12 | Status LED | Output | STATUS_LED | D1, R4 |
| GPIO33 | I2C SDA | I2C | I2C_SDA | U4, U6, R2 |
| GPIO34 | I2C SCL | I2C | I2C_SCL | U4, U6, R2 |
| GPIO35 | I2S BCLK | I2S | I2S_BCLK | U3, SP1 |
| GPIO36 | I2S LRCLK | I2S | I2S_LRCLK | U3, SP1 |
| GPIO37 | I2S DIN | I2S | I2S_DIN | U3 |
| GPIO38 | CAM_MIPI_DP | MIPI | CAM_MIPI | U2, J2 |
| GPIO39 | CAM_MIPI_DN | MIPI | CAM_MIPI | U2, J2 |
| GPIO40 | Camera XCLK | Output | CAM_XCLK | U2 |
| GPIO41 | Camera PCLK | Input | CAM_PCLK | U2 |
| GPIO42 | Camera VSYNC | Input | CAM_VSYNC | U2 |
| GPIO43 | Camera HSYNC | Input | CAM_HSYNC | U2 |
| GPIO44 | Camera D0 | Input | CAM_D0 | U2 |
| GPIO45 | Camera D1 | Input | CAM_D1 | U2 |
| GPIO46 | Camera D2 | Input | CAM_D2 | U2 |
| GPIO47 | Camera D3 | Input | CAM_D3 | U2 |
| GPIO48 | Camera D4 | Input | CAM_D4 | U2 |
| EN | Reset | Input | RESET | SW1 |
| XTAL | 40MHz Crystal | Clock | Y1 | C3, C4 |
| XTAL32K | 32.768kHz Crystal | Clock | Y2 | - |

### Power Budget
| Component | Voltage | Typical Current | Peak Current | Notes |
|-----------|---------|-----------------|--------------|-------|
| ESP32-S3 | 3.3V | 80mA | 200mA | WiFi active |
| OV5647 | 2.8V + 1.5V | 80mA | 100mA | Camera capture |
| MAX98357A | 3.3V | 5mA | 30mA | Audio playback |
| DRV2605 | 3.3V | 3mA | 15mA | Haptic active |
| CW2015 | 3.3V | 25uA | 50uA | Always on |
| MCP73831 | 5V | 500mA | 500mA | Charging only |
| NCP1117 | 5V->3.3V | - | 1A | Pass element |
| **TOTAL** | | **170mA** | **350mA** | Inference mode |
| **Battery Life** | | | | **~4 hours @ 500mA avg** |

### Thermal Targets
| Node | Max Temp | Current | Notes |
|------|----------|---------|-------|
| NCP1117 | 85C | 1A | Thermal shutdown at 125C |
| MCP73831 | 85C | 500mA | Internal thermal limit |
| L1 (10uH) | 70C | 470mA | Saturation current 2.2A |
| ESP32-S3 | 85C | 200mA | Internal thermal sensor |
| OV5647 | 70C | 100mA | Image quality degrades >70C |
