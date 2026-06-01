#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file live_classifier.py
@brief Real-time serial Wi-Fi sensing activity classifier using a rolling window.
"""

import os
import sys
import re
import time
import pickle
import argparse
from collections import deque

try:
    import serial
    import numpy as np
except ImportError:
    print("[ERROR] Missing required libraries. Please install them:")
    print("        pip install pyserial numpy")
    sys.exit(1)

# Regex to parse the structured serial data line
DATA_REGEX = re.compile(
    r"\[DATA\] RSSI:\s*(?P<rssi>-?\d+)\s*\|\s*Mean:\s*(?P<mean>-?\d+\.\d+)\s*\|\s*Var:\s*(?P<var>\d+\.\d+)\s*\|\s*Anomaly:\s*(?P<anomaly>\d+\.\d+)"
)

def run_classifier(port_name, baud_rate, model_path):
    # Load Model
    if not os.path.exists(model_path):
        print(f"[ERROR] Trained model file not found at '{model_path}'.")
        print("        Please run the training script first:")
        print("        python tools/train_classifier.py")
        sys.exit(1)
        
    print(f"[INFO] Loading ML Model from '{model_path}'...")
    try:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        print("🟢 Model loaded successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        sys.exit(1)

    # Open Serial
    print(f"[INFO] Connecting to serial port {port_name} at {baud_rate} baud...")
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=1.0)
        ser.reset_input_buffer()
        print("🟢 Serial connected! Waiting for data streams...")
    except serial.SerialException as e:
        print(f"[ERROR] Could not open serial port {port_name}: {e}")
        sys.exit(1)

    print("\n=======================================================")
    print("      LUMOS RF — REAL-TIME ACTIVITY CLASSIFICATION")
    print("=======================================================")
    print(" Press Ctrl+C to exit.")
    print("-------------------------------------------------------")

    # Rolling window buffers (15 samples = 1.5 seconds)
    window_size = 15
    rssi_history = deque(maxlen=window_size)
    var_history = deque(maxlen=window_size)
    mean_history = deque(maxlen=window_size)

    try:
        while True:
            if ser.in_waiting > 0:
                try:
                    line_bytes = ser.readline()
                    line = line_bytes.decode("utf-8", errors="ignore").strip()
                    
                    if line.startswith("[INFO]") or line.startswith("[WARN]") or line.startswith("[ALERT]"):
                        # Clear prediction line before printing logs to prevent overlapping text
                        sys.stdout.write("\r" + " " * 85 + "\r")
                        sys.stdout.flush()
                        print(line)
                        continue
                        
                    match = DATA_REGEX.search(line)
                    if match:
                        rssi = int(match.group("rssi"))
                        mean = float(match.group("mean"))
                        var = float(match.group("var"))
                        
                        # Add current values to buffers
                        rssi_history.append(rssi)
                        var_history.append(var)
                        mean_history.append(mean)
                        
                        # Once we have enough samples to construct a rolling feature set:
                        if len(rssi_history) == window_size:
                            # 1. Mean variance over the window
                            rolling_var_mean = np.mean(var_history)
                            
                            # 2. Maximum variance in the window
                            rolling_var_max = np.max(var_history)
                            
                            # 3. Mean absolute deviation of RSSI from its mean in the window
                            dev_list = [abs(r - m) for r, m in zip(rssi_history, mean_history)]
                            rolling_dev_mean = np.mean(dev_list)
                            
                            # 4. Amplitude of RSSI in the window
                            rolling_rssi_amp = np.max(rssi_history) - np.min(rssi_history)
                            
                            # Format features
                            features = np.array([[
                                rolling_var_mean,
                                rolling_var_max,
                                rolling_dev_mean,
                                rolling_rssi_amp
                            ]])
                            
                            # Predict
                            prediction = model.predict(features)[0]
                            probabilities = model.predict_proba(features)[0]
                            max_prob = max(probabilities) * 100
                            
                            sys.stdout.write(
                                f"\r🔮 PREDICTION: {prediction.upper():12} | Confidence: {max_prob:5.1f}% | Var Mean: {rolling_var_mean:6.4f}"
                            )
                            sys.stdout.flush()
                        else:
                            # Print loading state until buffer fills up
                            sys.stdout.write(f"\r[INFO] Filling rolling buffer... ({len(rssi_history)}/{window_size})")
                            sys.stdout.flush()
                except Exception as e:
                    continue
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n\n👋 Exiting Classifier.")
    finally:
        ser.close()

def main():
    parser = argparse.ArgumentParser(description="LUMOS RF — Real-Time Activity Classifier")
    parser.add_argument("--port", "-p", default="COM6", help="Serial port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--model", "-m", default=os.path.join("tools", "motion_model.pkl"), help="Path to trained model .pkl file")
    args = parser.parse_args()

    model_path = args.model
    if not os.path.exists(model_path) and os.path.exists("motion_model.pkl"):
        model_path = "motion_model.pkl"

    run_classifier(args.port, args.baud, model_path)

if __name__ == "__main__":
    main()
