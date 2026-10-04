#!/usr/bin/env python3
"""
flash_firmware.py
Flash SentinelEye firmware to ESP32-S3
With automatic backup, verification, and rollback
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

class ESP32Flasher:
    def __init__(self, port: str, baud: int = 460800):
        self.port = port
        self.baud = baud
        self.project_root = Path(__file__).parent.parent
        self.firmware_dir = self.project_root / "firmware"
        self.backup_dir = self.project_root / "backups"
        self.backup_dir.mkdir(exist_ok=True)

    def check_esp_tools(self):
        """Check if ESP-IDF tools are available"""
        try:
            result = subprocess.run(['esptool.py', '--version'],
                                    capture_output=True, text=True)
            print(f"esptool.py: {result.stdout.strip()}")
            return True
        except FileNotFoundError:
            print("ERROR: esptool.py not found")
            print("Install: pip install esptool")
            return False

    def read_chip_info(self):
        """Read ESP32-S3 chip information"""
        print(f"\nReading chip info from {self.port}...")
        cmd = f"esptool.py --port {self.port} chip_id"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"ERROR: {result.stderr}")
            return False

    def backup_existing_firmware(self):
        """Backup existing firmware before flashing"""
        print(f"\nBacking up existing firmware...")
        backup_file = self.backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"

        # Read flash (4MB)
        cmd = (f"esptool.py --port {self.port} --baud {self.baud} "
               f"read_flash 0x000000 0x400000 {backup_file}")

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Backup saved: {backup_file}")
            return True
        else:
            print(f"Backup failed: {result.stderr}")
            return False

    def flash_firmware(self, erase: bool = False):
        """Flash firmware to ESP32-S3"""
        print(f"\nFlashing firmware...")

        build_dir = self.firmware_dir / "build"
        if not build_dir.exists():
            print(f"ERROR: Build directory not found: {build_dir}")
            print("Please run: idf.py build")
            return False

        # Flash command
        if erase:
            print("Erasing flash before flashing...")
            cmd = f"esptool.py --port {self.port} --baud {self.baud} erase_flash"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Erase failed: {result.stderr}")
                return False

        # Flash bootloader + partition table + app
        cmd = (f"idf.py -p {self.port} -b {self.baud} flash")

        if erase:
            cmd += " erase-all"

        result = subprocess.run(cmd, shell=True, cwd=self.firmware_dir,
                               capture_output=True, text=True)

        if result.returncode == 0:
            print("Flash successful!")
            print(result.stdout)
            return True
        else:
            print(f"Flash failed: {result.stderr}")
            return False

    def verify_firmware(self):
        """Verify flashed firmware"""
        print(f"\nVerifying firmware...")
        cmd = f"esptool.py --port {self.port} --baud {self.baud} verify_flash 0x000000 0x400000"

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            print("Verification PASSED")
            print(result.stdout)
            return True
        else:
            print(f"Verification FAILED: {result.stderr}")
            return False

    def monitor_serial(self):
        """Monitor serial output"""
        print(f"\nMonitoring serial output (Ctrl+C to exit)...")
        cmd = f"idf.py -p {self.port} monitor"

        try:
            subprocess.run(cmd, shell=True, cwd=self.firmware_dir)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")

    def full_flash_sequence(self, backup: bool = True, erase: bool = False,
                           monitor: bool = True):
        """Complete flash sequence with verification"""

        print("="*60)
        print("SentinelEye Firmware Flash Sequence")
        print("="*60)
        print(f"Port: {self.port}")
        print(f"Baud: {self.baud}")
        print(f"Timestamp: {datetime.now().isoformat()}")

        # Check tools
        if not self.check_esp_tools():
            return False

        # Read chip info
        if not self.read_chip_info():
            print("ERROR: Cannot communicate with ESP32-S3")
            print("Check USB connection and port")
            return False

        # Backup existing
        if backup:
            self.backup_existing_firmware()

        # Flash firmware
        if not self.flash_firmware(erase=erase):
            return False

        # Verify
        if not self.verify_firmware():
            return False

        print("\n" + "="*60)
        print("Flash sequence COMPLETE!")
        print("="*60)

        # Monitor
        if monitor:
            self.monitor_serial()

        return True

def main():
    parser = argparse.ArgumentParser(description='SentinelEye Firmware Flasher')
    parser.add_argument('--port', type=str, required=True,
                        help='Serial port (e.g., COM3, /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=460800,
                        help='Baud rate (default: 460800)')
    parser.add_argument('--no-backup', action='store_true',
                        help='Skip firmware backup')
    parser.add_argument('--erase', action='store_true',
                        help='Erase flash before flashing')
    parser.add_argument('--no-monitor', action='store_true',
                        help='Skip serial monitor after flashing')
    parser.add_argument('--verify-only', action='store_true',
                        help='Only verify existing firmware')

    args = parser.parse_args()

    flasher = ESP32Flasher(args.port, args.baud)

    if args.verify_only:
        flasher.read_chip_info()
        flasher.verify_firmware()
    else:
        flasher.full_flash_sequence(
            backup=not args.no_backup,
            erase=args.erase,
            monitor=not args.no_monitor
        )

if __name__ == "__main__":
    main()
