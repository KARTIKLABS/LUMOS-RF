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
import socket
import select
import json

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

def run_recording(mode, port_name, baud_rate, label, duration_s, node_id_filter=None):
    """
    Connects to the ESP8266 via Serial or UDP, waits for calibration, and records labeled telemetry.
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
    print(f"Mode:         {mode.upper()}")
    print(f"Target Label: {label.upper()}")
    print(f"Duration:     {duration_s} seconds")
    print(f"Output File:  {output_filename}")
    print("=======================================================")
    
    ser = None
    sock = None
    
    if mode == "udp":
        try:
            udp_port = int(port_name)
        except ValueError:
            udp_port = 5001
            print(f"[WARN] Invalid UDP port format '{port_name}'. Defaulting to port {udp_port}.")
            
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", udp_port))
            print(f"\n[INFO] UDP socket bound to port {udp_port}. Waiting for ESP8266 to finish baseline calibration...")
            print("[INFO] (Please stay completely still while the node calibrates...)")
        except Exception as e:
            print(f"[ERROR] Could not bind UDP socket: {e}")
            return
            
        # Wait for the first packet from the node (signifies sensing mode is active)
        calibrated = False
        while not calibrated:
            ready = select.select([sock], [], [], 0.5)
            if ready[0]:
                try:
                    data, addr = sock.recvfrom(1024)
                    message = data.decode("utf-8").strip()
                    payload = json.loads(message)
                    node_id = payload.get("node_id")
                    
                    if node_id_filter is None or node_id == node_id_filter:
                        calibrated = True
                        print(f"\n\n[SUCCESS] Node '{node_id}' Calibrated and Streaming!")
                except Exception:
                    pass
            else:
                time.sleep(0.05)
    else:
        # Open Serial connection
        try:
            ser = serial.Serial(port_name, baud_rate, timeout=1.0)
            ser.reset_input_buffer()
        except serial.SerialException as e:
            print(f"[ERROR] Could not open serial port {port_name}: {e}")
            return

        print("\n[INFO] Connected to ESP8266. Waiting for boot and baseline calibration to complete...")
        print("[INFO] (Please stay completely still while the node calibrates its noise floor...)")
        
        calibrated = False
        while not calibrated:
            if ser.in_waiting > 0:
                try:
                    line_bytes = ser.readline()
                    line = line_bytes.decode("utf-8", errors="ignore").strip()
                    if "System entered SENSING mode" in line or "[DATA]" in line:
                        calibrated = True
                        print("\n\n[SUCCESS] ESP8266 Calibrated and Ready!")
                    elif "Calibrating baseline" in line:
                        sys.stdout.write(f"\r{line}")
                        sys.stdout.flush()
                except Exception:
                    pass
            else:
                time.sleep(0.05)
        # Clear serial input buffer to remove calibration backlog
        ser.reset_input_buffer()

    # 3-second countdown to let user position themselves
    print("\nPrepare for recording...")
    for i in range(3, 0, -1):
        print(f"Starting in {i}...")
        time.sleep(1.0)
    print("[RECORDING STARTED]")
    
    samples_collected = 0
    start_time = time.time()
    end_time = start_time + duration_s
    
    # Open CSV writer
    try:
        with open(output_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["time_offset_s", "rssi", "rssi_mean", "variance", "anomaly_score", "class_label"])
            
            # Record loop
            while time.time() < end_time:
                if mode == "udp":
                    ready = select.select([sock], [], [], 0.1)
                    if ready[0]:
                        try:
                            data, addr = sock.recvfrom(1024)
                            message = data.decode("utf-8").strip()
                            payload = json.loads(message)
                            
                            node_id = payload.get("node_id")
                            if node_id_filter and node_id != node_id_filter:
                                continue
                                
                            rssi = int(payload.get("rssi", -127))
                            mean = float(payload.get("mean", 0.0))
                            var = float(payload.get("var", 0.0))
                            anomaly = float(payload.get("anomaly", 0.0))
                            
                            elapsed = time.time() - start_time
                            
                            # Log row to CSV
                            writer.writerow([f"{elapsed:.3f}", rssi, mean, var, anomaly, label])
                            samples_collected += 1
                            
                            # Render progress bar
                            percent = (elapsed / duration_s) * 100
                            bar_len = 30
                            filled_len = int(bar_len * elapsed / duration_s)
                            bar = '=' * filled_len + '-' * (bar_len - filled_len)
                            
                            sys.stdout.write(f"\r[{bar}] {percent:5.1f}% | Samples: {samples_collected} | Node: {node_id} | RSSI: {rssi:4d}")
                            sys.stdout.flush()
                        except Exception:
                            continue
                    else:
                        time.sleep(0.01)
                else:
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
                                
                                # Render progress bar
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
        print("\n[WARN] Recording interrupted by user.")
    finally:
        if mode == "udp" and sock:
            sock.close()
        elif ser:
            ser.close()
        
    print("\n[SUCCESS] RECORDING COMPLETE!")
    print(f"[INFO] Saved {samples_collected} samples to '{output_filename}'")
    
    # Calculate statistics
    if samples_collected > 0:
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
    parser.add_argument("--mode", choices=["serial", "udp"], default="serial", help="Data source mode (serial or udp)")
    parser.add_argument("--port", "-p", default="COM6", help="Serial port (e.g. COM6) or UDP port (e.g. 5001)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200, serial mode only)")
    parser.add_argument("--node", "-n", default=None, help="Node ID filter (udp mode only)")
    parser.add_argument("--label", "-l", help="Activity label (e.g., walking, idle, waving_hand)")
    parser.add_argument("--duration", "-d", type=int, default=30, help="Recording duration in seconds (default: 30)")
    args = parser.parse_args()

    label = args.label
    if not label:
        try:
            label = input("Enter activity label (e.g., idle, walking, waving_hand, typing): ").strip().lower()
            label = re.sub(r'[^a-z0-9_]', '', label)
            if not label:
                print("[ERROR] Invalid label.")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)

    run_recording(args.mode, args.port, args.baud, label, args.duration, args.node)

if __name__ == "__main__":
    main()
