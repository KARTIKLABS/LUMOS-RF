#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file dataset_generator.py
@brief CLI tool for capturing and labeling real-time Wi-Fi sensing sessions 
       to create datasets for TinyML model training.
"""

import os
import sys
import re
import csv
import time
import argparse

try:
    import serial
except ImportError:
    print("[ERROR] Missing required libraries. Please install them using:")
    print("        pip install pyserial")
    sys.exit(1)

# Regex to parse the structured serial data line
DATA_REGEX = re.compile(
    r"\[DATA\] RSSI:\s*(?P<rssi>-?\d+)\s*\|\s*Mean:\s*(?P<mean>-?\d+\.\d+)\s*\|\s*Var:\s*(?P<var>\d+\.\d+)\s*\|\s*Anomaly:\s*(?P<anomaly>\d+\.\d+)\s*\|\s*Level:\s*(?P<level>\w+)"
)

def run_recording(port_name, baud_rate, label, duration_s):
    """
    Connects to the ESP8266, counts down, and logs data for the given duration.
    """
    # Create datasets directory if it doesn't exist
    dataset_dir = "datasets"
    if not os.path.exists(dataset_dir):
        os.makedirs(dataset_dir)
        print(f"[INFO] Created directory: {dataset_dir}")
        
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    output_filename = os.path.join(dataset_dir, f"dataset_{label}_{timestamp_str}.csv")
    
    print("\n=======================================================")
    print("      LUMOS RF — TINYML DATASET CAPTURE TOOL")
    print("=======================================================")
    print(f"Target Label: {label.upper()}")
    print(f"Duration:     {duration_s} seconds")
    print(f"Output File:  {output_filename}")
    print("=======================================================")
    
    # Open Serial connection
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=1.0)
        ser.reset_input_buffer()
    except serial.SerialException as e:
        print(f"[ERROR] Could not open serial port {port_name}: {e}")
        return

    print("\n[INFO] Connected to ESP8266. Waiting for boot and baseline calibration to complete...")
    print("[INFO] (Please stay completely still while the node calibrates its noise floor...)")
    
    # Wait until we see "[INFO] System entered SENSING mode." or the first "[DATA]" line
    calibrated = False
    while not calibrated:
        if ser.in_waiting > 0:
            try:
                line_bytes = ser.readline()
                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if "System entered SENSING mode" in line or "[DATA]" in line:
                    calibrated = True
                    print("\n\n🟢 ESP8266 Calibrated and Ready!")
                elif "Calibrating baseline" in line:
                    sys.stdout.write(f"\r{line}")
                    sys.stdout.flush()
            except Exception as e:
                pass
        else:
            time.sleep(0.05)

    # Clear input buffer to remove any old data accumulated during calibration/wait
    ser.reset_input_buffer()

    # 3-second countdown to let user position themselves
    print("\nPrepare for recording...")
    for i in range(3, 0, -1):
        print(f"Starting in {i}...")
        time.sleep(1.0)
    print("🔴 RECORDING STARTED!")
    
    samples_collected = 0
    start_time = time.time()
    end_time = start_time + duration_s
    
    # Open CSV writer
    try:
        with open(output_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header fields
            writer.writerow(["time_offset_s", "rssi", "rssi_mean", "variance", "anomaly_score", "class_label"])
            
            # Record loop
            while time.time() < end_time:
                if ser.in_waiting > 0:
                    try:
                        line_bytes = ser.readline()
                        line = line_bytes.decode("utf-8", errors="ignore").strip()
                        
                        match = DATA_REGEX.search(line)
                        if match:
                            rssi = int(match.group("rssi"))
                            mean = float(match.group("mean"))
                            var = float(match.group("var"))
                            anomaly = float(match.group("anomaly"))
                            
                            elapsed = time.time() - start_time
                            
                            # Log row to CSV
                            writer.writerow([f"{elapsed:.3f}", rssi, mean, var, anomaly, label])
                            samples_collected += 1
                            
                            # Render simple text-based progress bar in terminal
                            percent = (elapsed / duration_s) * 100
                            bar_len = 30
                            filled_len = int(bar_len * elapsed / duration_s)
                            bar = '=' * filled_len + '-' * (bar_len - filled_len)
                            
                            sys.stdout.write(f"\r[{bar}] {percent:5.1f}% | Samples: {samples_collected} | RSSI: {rssi:4d}")
                            sys.stdout.flush()
                    except Exception as e:
                        print(f"\n[WARN] Error reading line: {e}")
                        continue
                else:
                    time.sleep(0.01)
                    
    except KeyboardInterrupt:
        print("\n⚠️ Recording interrupted by user.")
    finally:
        ser.close()
        
    print("\n🟢 RECORDING COMPLETE!")
    print(f"[INFO] Saved {samples_collected} samples to '{output_filename}'")
    
    # Calculate statistics
    if samples_collected > 0:
        # Re-read data to calculate summary statistics
        with open(output_filename, 'r') as f:
            reader = csv.reader(f)
            next(reader) # Skip header
            rssi_vals = []
            var_vals = []
            for row in reader:
                rssi_vals.append(float(row[1]))
                var_vals.append(float(row[3]))
            
            print(f"Statistics for '{label.upper()}':")
            print(f"  - Average RSSI:     {sum(rssi_vals)/len(rssi_vals):.2f} dBm")
            print(f"  - Average Variance: {sum(var_vals)/len(var_vals):.4f} dBm^2")
    print("=======================================================\n")

def main():
    parser = argparse.ArgumentParser(description="LUMOS RF — TinyML Dataset Capture Tool")
    parser.add_argument("--port", "-p", default="COM6", help="Serial port (e.g. COM6 or /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--label", "-l", help="Activity label (e.g., walking, idle, waving_hand)")
    parser.add_argument("--duration", "-d", type=int, default=30, help="Recording duration in seconds (default: 30)")
    args = parser.parse_args()

    # If parameters not provided on command line, prompt interactively
    label = args.label
    if not label:
        try:
            label = input("Enter activity label (e.g., idle, walking, waving_hand, typing): ").strip().lower()
            # Clean label to be safe for filenames
            label = re.sub(r'[^a-z0-9_]', '', label)
            if not label:
                print("[ERROR] Invalid label.")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)

    run_recording(args.port, args.baud, label, args.duration)

if __name__ == "__main__":
    main()
