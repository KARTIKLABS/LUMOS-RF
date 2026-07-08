#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file test_trilateration.py
@brief Test harness to validate the mathematical trilateration engine and Kalman filter.
"""

import sys
import numpy as np
from trilateration_engine import TrilaterationEngine, Kalman3D

def run_tests():
    print("=======================================================")
    print("        LUMOS RF 3D — TRILATERATION ENGINE TEST        ")
    print("=======================================================")
    
    # 1. Define nodes configuration
    node_configs = {
        "node_1": {"x": 0.0, "y": 0.0, "z": 1.0},
        "node_2": {"x": 5.0, "y": 0.0, "z": 1.0},
        "node_3": {"x": 0.0, "y": 5.0, "z": 1.8},
        "node_4": {"x": 5.0, "y": 5.0, "z": 1.8}
    }
    
    tx_power = -40.0
    path_loss_exponent = 2.0
    bounds = [(0.0, 5.0), (0.0, 5.0), (0.0, 3.0)]
    
    # Instantiate engine
    engine = TrilaterationEngine(node_configs, tx_power, path_loss_exponent, bounds)
    kf = Kalman3D(process_noise=0.05, measurement_noise=0.5)
    
    # Define a target coordinate to track
    actual_pos = np.array([2.5, 3.0, 1.2])
    print(f"[TEST 1] Target Coordinate: X={actual_pos[0]:.2f}m, Y={actual_pos[1]:.2f}m, Z={actual_pos[2]:.2f}m")
    
    # 2. Compute true distances and corresponding perfect RSSI values
    node_rssis = {}
    print("\nSimulating Perfect Signals:")
    for nid, coords in node_configs.items():
        pos = np.array([coords["x"], coords["y"], coords["z"]])
        dist = np.sqrt(np.sum((actual_pos - pos) ** 2))
        
        # Path loss formula: RSSI = RSSI_0 - 10 * n * log10(d)
        rssi = tx_power - 10.0 * path_loss_exponent * np.log10(dist)
        node_rssis[nid] = rssi
        print(f"  Node {nid}: Dist = {dist:5.2f}m => RSSI = {rssi:6.2f} dBm")
        
    # 3. Solve trilateration
    estimated_pos = engine.locate(node_rssis)
    print(f"\n[RESULT 1] Calculated Coordinates:")
    print(f"  Estimated: X={estimated_pos[0]:.4f}m, Y={estimated_pos[1]:.4f}m, Z={estimated_pos[2]:.4f}m")
    error = np.sqrt(np.sum((estimated_pos - actual_pos) ** 2))
    print(f"  Absolute Euclidean Error: {error:.6f} meters")
    
    assert error < 0.01, f"[FAIL] Localization error is too high: {error:.6f}m"
    print("  [PASS] Solver matches exact coordinates under perfect signal.")

    # 4. Simulate noisy signals (add normal distributed noise to RSSI)
    print("\n-------------------------------------------------------")
    print("[TEST 2] Simulating Noisy Signal Fluctuations (±3 dBm):")
    np.random.seed(42) # For reproducible noise
    
    total_error = 0
    total_kf_error = 0
    steps = 10
    
    for step in range(steps):
        noisy_rssis = {}
        for nid, clean_rssi in node_rssis.items():
            noise = np.random.normal(0, 1.5) # std deviation of 1.5 dBm
            noisy_rssis[nid] = clean_rssi + noise
            
        est_noisy = engine.locate(noisy_rssis)
        est_smooth = kf.update(est_noisy)
        
        err_raw = np.sqrt(np.sum((est_noisy - actual_pos) ** 2))
        err_kf = np.sqrt(np.sum((est_smooth - actual_pos) ** 2))
        
        total_error += err_raw
        total_kf_error += err_kf
        
        print(f"  Step {step+1:2d} | Raw Err: {err_raw:5.3f}m | Kalman Smooth Err: {err_kf:5.3f}m")
        
    avg_raw_err = total_error / steps
    avg_kf_err = total_kf_error / steps
    print(f"\n[RESULT 2] Summary after {steps} iterations:")
    print(f"  Average Raw Trilateration Error:  {avg_raw_err:.4f} meters")
    print(f"  Average Kalman-Smoothed Error:    {avg_kf_err:.4f} meters")
    
    assert avg_kf_err < avg_raw_err, "[FAIL] Kalman Filter did not reduce average positioning error!"
    print("  [PASS] Kalman filter successfully smoothed trajectory noise.")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
