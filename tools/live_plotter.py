#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file live_plotter.py
@brief Python script for real-time visualization of serial telemetry from LUMOS RF.
"""

import sys
import re
import time
import argparse
import threading
from collections import deque

try:
    import serial
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
except ImportError:
    print("[ERROR] Missing required libraries. Please install them using:")
    print("        pip install pyserial matplotlib")
    sys.exit(1)

# Regex to parse the structured serial data line:
# Example: [DATA] RSSI: -60 | Mean: -60.12 | Var: 0.0450 | Anomaly: 0.90 | Level: IDLE
DATA_REGEX = re.compile(
    r"\[DATA\] RSSI:\s*(?P<rssi>-?\d+)\s*\|\s*Mean:\s*(?P<mean>-?\d+\.\d+)\s*\|\s*Var:\s*(?P<var>\d+\.\d+)\s*\|\s*Anomaly:\s*(?P<anomaly>\d+\.\d+)\s*\|\s*Level:\s*(?P<level>\w+)"
)

# Shared data structures between serial thread and plotter
data_queue = deque(maxlen=200) # History buffer size for plot
latest_state = {"rssi": 0, "mean": 0.0, "var": 0.0, "anomaly": 0.0, "level": "IDLE"}
lock = threading.Lock()
running = True

def serial_reader_thread(port_name, baud_rate):
    """
    Background thread to read and parse serial data from the ESP8266.
    """
    global running, latest_state
    print(f"[INFO] Connecting to serial port {port_name} at {baud_rate} baud...")
    
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=1.0)
        # Clear buffer
        ser.reset_input_buffer()
        print(f"[INFO] Connected! Listening for LUMOS RF logs...")
    except serial.SerialException as e:
        print(f"[ERROR] Could not open serial port {port_name}: {e}")
        running = False
        return

    while running:
        try:
            if ser.in_waiting > 0:
                line_bytes = ser.readline()
                try:
                    line = line_bytes.decode("utf-8", errors="ignore").strip()
                except Exception:
                    continue
                
                # Check for standard print messages
                if line.startswith("[BOOT]") or line.startswith("[INFO]") or line.startswith("[WARN]") or line.startswith("[ERROR]"):
                    print(f"ESP8266: {line}")
                elif line.startswith("[ALERT]"):
                    print(f"\033[91mESP8266 ALERT: {line}\033[0m") # Red alert text
                
                # Check if it matches the data pattern
                match = DATA_REGEX.search(line)
                if match:
                    # Extract variables
                    rssi = int(match.group("rssi"))
                    mean = float(match.group("mean"))
                    var = float(match.group("var"))
                    anomaly = float(match.group("anomaly"))
                    level = match.group("level")
                    
                    timestamp = time.time()
                    
                    with lock:
                        latest_state = {
                            "rssi": rssi,
                            "mean": mean,
                            "var": var,
                            "anomaly": anomaly,
                            "level": level
                        }
                        data_queue.append((timestamp, rssi, mean, var, anomaly, level))
            else:
                time.sleep(0.01) # Avoid burning CPU
        except Exception as e:
            print(f"[ERROR] Serial read error: {e}")
            break
            
    ser.close()
    print("[INFO] Serial connection closed.")

def main():
    global running
    parser = argparse.ArgumentParser(description="LUMOS RF — Real-time Wi-Fi Sensing Plotter")
    parser.add_argument("--port", "-p", default="COM6", help="Serial port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--window", "-w", type=int, default=100, help="Plot window size in samples")
    args = parser.parse_args()

    # Start serial reader thread
    reader = threading.Thread(target=serial_reader_thread, args=(args.port, args.baud), daemon=True)
    reader.start()

    # Wait for the first data point to arrive or thread to error
    time.sleep(1.0)
    if not running:
        sys.exit(1)

    # Setup the Plot
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=False)
    fig.suptitle("LUMOS RF — Real-Time Signal Disturbance Telemetry", fontsize=14, color="#00E5FF")

    # Double panel plotting setup
    # Subplot 1: RSSI and Moving Average
    rssi_line, = ax1.plot([], [], label="Raw RSSI (dBm)", color="#FF007F", alpha=0.5, linewidth=1.5)
    mean_line, = ax1.plot([], [], label="Mean RSSI (dBm)", color="#00FFCC", linewidth=2.0)
    ax1.set_ylabel("RSSI (dBm)", color="white")
    ax1.grid(True, color="#333333")
    ax1.legend(loc="upper left")
    
    # Subplot 2: RSSI Variance and Detection Thresholds
    var_line, = ax2.plot([], [], label="RSSI Variance", color="#FFFF00", linewidth=1.8)
    ax2.set_ylabel("Variance ($dBm^2$)", color="white")
    ax2.set_xlabel("Time (s)", color="white")
    ax2.grid(True, color="#333333")
    
    # Add horizontal threshold markers (values from Config.h)
    ax2.axhline(y=0.15, color="#00FF00", linestyle="--", alpha=0.6, label="Slight Threshold (0.15)")
    ax2.axhline(y=1.20, color="#FF9900", linestyle="--", alpha=0.6, label="Moderate Threshold (1.20)")
    ax2.axhline(y=4.50, color="#FF0000", linestyle="--", alpha=0.6, label="Heavy Threshold (4.50)")
    ax2.legend(loc="upper left")

    # Text overlay elements
    status_text = fig.text(0.15, 0.02, "Level: IDLE", fontsize=16, fontweight="bold", color="#00FF00")
    anomaly_text = fig.text(0.55, 0.02, "Anomaly Score: 1.00", fontsize=14, color="white")

    # Define color mappings for the motion levels
    color_map = {
        "IDLE": "#00FF00",       # Green
        "SLIGHT": "#FFFF00",     # Yellow
        "MODERATE": "#FF9900",   # Orange
        "HEAVY": "#FF0000"       # Red
    }

    start_time = time.time()

    def update_plot(frame):
        with lock:
            if not data_queue:
                return rssi_line, mean_line, var_line

            # Fetch snapshot of current queue
            points = list(data_queue)
            state = latest_state.copy()

        # Limit window to the user specified sample count
        if len(points) > args.window:
            points = points[-args.window:]

        # Extract axes values
        times = [pt[0] - start_time for pt in points]
        rssis = [pt[1] for pt in points]
        means = [pt[2] for pt in points]
        vars_ = [pt[3] for pt in points]

        # Update lines data
        rssi_line.set_data(times, rssis)
        mean_line.set_data(times, means)
        var_line.set_data(times, vars_)

        # Rescale axes dynamically
        ax1.relim()
        ax1.autoscale_view()
        ax2.relim()
        ax2.autoscale_view()
        
        # Keep variance y-limits sensible
        current_max_var = max(vars_) if vars_ else 0
        ax2.set_ylim(0, max(6.0, current_max_var * 1.2))

        # Update overlay texts
        lvl = state["level"]
        lbl_color = color_map.get(lvl, "white")
        status_text.set_text(f"Activity Level: {lvl}")
        status_text.set_color(lbl_color)
        anomaly_text.set_text(f"Anomaly Score: {state['anomaly']:.2f}")

        return rssi_line, mean_line, var_line

    # Use FuncAnimation for real-time update loop
    ani = animation.FuncAnimation(fig, update_plot, interval=100, blit=False, cache_frame_data=False)

    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        print("[INFO] Terminating plotter window...")

if __name__ == "__main__":
    main()
