#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file mock_node_client.py
@brief Simulates multiple wireless nodes streaming UDP data for end-to-end local testing.
"""

import sys
import json
import time
import socket
import math
import random

def main():
    print("=======================================================")
    print("        LUMOS RF 3D — NODE TELEMETRY SIMULATOR         ")
    print("=======================================================")
    
    # Load configuration
    try:
        with open("tools/config.json", "r") as f:
            config = json.load(f)
        print("[INFO] Config loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to load config.json: {e}")
        sys.exit(1)
        
    nodes = config["nodes"]
    tx_power = config.get("tx_power_1m", -42.0)
    n = config.get("path_loss_exponent", 2.2)
    
    udp_ip = "127.0.0.1"
    udp_port = config.get("udp_port", 5001)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"[INFO] Streaming mock nodes packets to {udp_ip}:{udp_port}")
    print("[INFO] Simulating a person walking in a circular trajectory...")
    print("[INFO] Press Ctrl+C to stop simulation.")
    print("-------------------------------------------------------")
    
    theta = 0.0
    start_time = time.time()
    
    try:
        while True:
            # 1. Update target coordinate along a circular path inside the room
            # Room center is roughly (2.5, 2.5), bounds are 0-5m.
            target_x = 2.5 + 1.5 * math.cos(theta)
            target_y = 2.5 + 1.5 * math.sin(theta)
            target_z = 1.0 + 0.3 * math.sin(2 * theta)
            
            theta += 0.05 # Increment angle
            
            # Send packet for each node
            for nid, coords in nodes.items():
                # Compute true distance from target to anchor node
                dx = target_x - coords["x"]
                dy = target_y - coords["y"]
                dz = target_z - coords["z"]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                
                # Compute RSSI using Path Loss model + noise
                noise = random.normalvariate(0, 0.8) # ±1.5 dBm signal noise
                rssi = tx_power - 10.0 * n * math.log10(max(dist, 0.1)) + noise
                rssi = int(round(rssi))
                
                # Compute motion levels: variance increases when closer to the node
                # Let's say closer proximity = higher signal variance
                proximity = 1.0 / (dist + 0.5)
                variance = proximity * 0.8 + random.uniform(0, 0.1)
                
                anomaly = variance * 4.5
                
                if variance > 0.8:
                    level = "HEAVY"
                elif variance > 0.5:
                    level = "MODERATE"
                elif variance > 0.2:
                    level = "SLIGHT"
                else:
                    level = "IDLE"
                
                ms = int((time.time() - start_time) * 1000)
                
                packet = {
                    "node_id": nid,
                    "ms": ms,
                    "rssi": rssi,
                    "mean": float(f"{rssi + random.uniform(-0.5, 0.5):.2f}"),
                    "var": float(f"{variance:.4f}"),
                    "anomaly": float(f"{anomaly:.2f}"),
                    "level": level
                }
                
                message = json.dumps(packet)
                sock.sendto(message.encode("utf-8"), (udp_ip, udp_port))
                
            # Print target position status
            sys.stdout.write(f"\r[SIM] Actual Target Position -> X: {target_x:.2f}m, Y: {target_y:.2f}m, Z: {target_z:.2f}m | Sent telemetry for {len(nodes)} nodes.")
            sys.stdout.flush()
            
            time.sleep(0.1) # 10Hz transmission rate
            
    except KeyboardInterrupt:
        print("\n\n[INFO] Simulation stopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
