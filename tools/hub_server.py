#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file hub_server.py
@brief Central UDP aggregator, trilateration runner, and web server for LUMOS RF 3D.
"""

import os
import sys
import json
import time
import socket
import select
import threading
import http.server
import socketserver
from datetime import datetime

# Import the Trilateration engine
from trilateration_engine import TrilaterationEngine, Kalman3D

# Global configuration and state
running = True
system_config = {}
active_nodes_data = {} # node_id -> telemetry dict
latest_position = {"x": 2.5, "y": 2.5, "z": 1.2, "x_smooth": 2.5, "y_smooth": 2.5, "z_smooth": 1.2, "active": False}
data_lock = threading.Lock()
csv_file_handle = None
csv_writer = None

def load_config():
    global system_config
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "r") as f:
            system_config = json.load(f)
        print(f"[BOOT] Loaded configuration from {config_path}")
    except Exception as e:
        print(f"[ERROR] Failed to load configuration: {e}")
        sys.exit(1)

def setup_csv_logger():
    global csv_file_handle, csv_writer
    datasets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "datasets")
    os.makedirs(datasets_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(datasets_dir, f"hub_stream_{timestamp}.csv")
    
    try:
        csv_file_handle = open(filepath, "w", newline="", encoding="utf-8")
        import csv
        csv_writer = csv.writer(csv_file_handle)
        csv_writer.writerow([
            "timestamp_ms", "node_id", "raw_rssi", "mean_rssi", "variance", 
            "anomaly_score", "activity_level", "pos_x", "pos_y", "pos_z",
            "pos_x_smooth", "pos_y_smooth", "pos_z_smooth"
        ])
        print(f"[BOOT] Logging session data to: {filepath}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize CSV logger: {e}")

def udp_receiver_thread():
    global running, active_nodes_data
    
    host = "0.0.0.0"
    port = system_config.get("udp_port", 5001)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Allow address reuse
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind((host, port))
        sock.setblocking(0)
        print(f"[BOOT] UDP Receiver bound to {host}:{port}")
    except Exception as e:
        print(f"[ERROR] UDP Socket bind failed: {e}")
        running = False
        return

    # Wait for packets
    while running:
        ready = select.select([sock], [], [], 0.5)
        if ready[0]:
            try:
                data, addr = sock.recvfrom(1024)
                message = data.decode("utf-8").strip()
                
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    continue # Ignore invalid JSON
                
                node_id = payload.get("node_id")
                if not node_id:
                    continue
                
                # Update node record
                with data_lock:
                    active_nodes_data[node_id] = {
                        "rssi": int(payload.get("rssi", -127)),
                        "mean": float(payload.get("mean", 0.0)),
                        "variance": float(payload.get("var", 0.0)),
                        "anomaly": float(payload.get("anomaly", 0.0)),
                        "level": payload.get("level", "IDLE"),
                        "last_seen": time.time(),
                        "ip": addr[0]
                    }
            except Exception as e:
                # Log socket receive error but do not crash
                pass

    sock.close()
    print("[INFO] UDP Receiver socket closed.")

def processing_engine_thread():
    global running, latest_position
    
    # Initialize Engine
    nodes_config = system_config["nodes"]
    tx_power = system_config.get("tx_power_1m", -42.0)
    path_loss_exp = system_config.get("path_loss_exponent", 2.2)
    
    bounds = [
        (system_config["room_bounds"]["x_min"], system_config["room_bounds"]["x_max"]),
        (system_config["room_bounds"]["y_min"], system_config["room_bounds"]["y_max"]),
        (system_config["room_bounds"]["z_min"], system_config["room_bounds"]["z_max"])
    ]
    
    engine = TrilaterationEngine(nodes_config, tx_power, path_loss_exp, bounds)
    
    # Kalman filters parameters
    k_proc = system_config["kalman"].get("process_noise", 0.05)
    k_meas = system_config["kalman"].get("measurement_noise", 0.5)
    kf = Kalman3D(k_proc, k_meas)
    
    print("[BOOT] Spatial processing engine initialized.")
    
    while running:
        time.sleep(0.1) # 10Hz calculation loop
        
        current_time = time.time()
        rssi_inputs = {}
        node_states = {}
        
        # Collect recent measurements
        with data_lock:
            for nid, node_data in list(active_nodes_data.items()):
                # Timeout nodes not seen in last 2.5 seconds
                if current_time - node_data["last_seen"] < 2.5:
                    rssi_inputs[nid] = node_data["rssi"]
                    node_states[nid] = node_data
                else:
                    # Stale node
                    pass
        
        if len(rssi_inputs) >= 3:
            # We can calculate coordinates!
            coords = engine.locate(rssi_inputs)
            coords_smooth = kf.update(coords)
            
            with data_lock:
                latest_position.update({
                    "x": float(coords[0]),
                    "y": float(coords[1]),
                    "z": float(coords[2]),
                    "x_smooth": float(coords_smooth[0]),
                    "y_smooth": float(coords_smooth[1]),
                    "z_smooth": float(coords_smooth[2]),
                    "active": True
                })
            
            # Log all node records with current estimated position
            if csv_writer and csv_file_handle:
                for nid, n_data in node_states.items():
                    csv_writer.writerow([
                        int(time.time() * 1000),
                        nid,
                        n_data["rssi"],
                        n_data["mean"],
                        n_data["variance"],
                        n_data["anomaly"],
                        n_data["level"],
                        f"{coords[0]:.3f}",
                        f"{coords[1]:.3f}",
                        f"{coords[2]:.3f}",
                        f"{coords_smooth[0]:.3f}",
                        f"{coords_smooth[1]:.3f}",
                        f"{coords_smooth[2]:.3f}"
                    ])
                csv_file_handle.flush()
        else:
            with data_lock:
                latest_position["active"] = False

# HTTP Static & SSE Server Handler
class DashboardRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Prevent SSE connection logging from spamming the console
        if "api/stream" in self.path:
            return
        super().log_message(format, *args)
        
    def do_GET(self):
        web_dir = os.path.join(os.path.dirname(__file__), "web")
        
        # 1. API: Configuration Endpoint
        if self.path == "/api/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(system_config).encode('utf-8'))
            return
            
        # 2. API: Server-Sent Events Real-Time Data Stream
        elif self.path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            try:
                while running:
                    time.sleep(0.1) # 10Hz streaming interval
                    
                    with data_lock:
                        # Filter active nodes for transmission
                        now = time.time()
                        online_nodes = {}
                        for nid, ndata in active_nodes_data.items():
                            if now - ndata["last_seen"] < 2.5:
                                online_nodes[nid] = {
                                    "rssi": ndata["rssi"],
                                    "mean": ndata["mean"],
                                    "variance": ndata["variance"],
                                    "anomaly": ndata["anomaly"],
                                    "level": ndata["level"]
                                }
                        
                        payload = {
                            "nodes": online_nodes,
                            "target": latest_position
                        }
                        
                    data_str = f"data: {json.dumps(payload)}\n\n"
                    self.wfile.write(data_str.encode('utf-8'))
                    self.wfile.flush()
            except (ConnectionResetError, ConnectionAbortedError, socket.error):
                # Silent catch when browser disconnects / tab is closed
                pass
            return
            
        # 3. Static Files Serving
        else:
            path_cleaned = self.path.split('?')[0].lstrip('/')
            if path_cleaned == "" or path_cleaned == "index.html":
                filepath = os.path.join(web_dir, "index.html")
                content_type = "text/html"
            elif path_cleaned == "style.css":
                filepath = os.path.join(web_dir, "style.css")
                content_type = "text/css"
            elif path_cleaned == "app.js":
                filepath = os.path.join(web_dir, "app.js")
                content_type = "application/javascript"
            else:
                self.send_error(404, "File Not Found")
                return

            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, f"File {path_cleaned} Not Found")

def start_http_server():
    server_port = system_config.get("web_port", 8080)
    handler = DashboardRequestHandler
    
    # Threading server allows multiple connections (SSE + static requests)
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        
    httpd = ThreadedHTTPServer(("0.0.0.0", server_port), handler)
    print(f"[BOOT] HTTP Web Server running at http://localhost:{server_port}")
    
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    return httpd

def print_terminal_dashboard():
    """
    Prints a beautiful text dashboard in the terminal window.
    """
    sys.stdout.write("\033[H\033[J") # Clear screen
    print("=====================================================================")
    print("                      LUMOS RF — CENTRAL HUB SERVER                  ")
    print("=====================================================================")
    print(f" UDP Receiver: port 5001  |  Web UI: http://localhost:8080")
    print(" Press Ctrl+C to stop.")
    print("---------------------------------------------------------------------")
    
    with data_lock:
        print("ACTIVE RECEIVER NODES:")
        if not active_nodes_data:
            print("  Waiting for node UDP packets...")
        else:
            print(f"  {'Node ID':12} | {'IP Address':15} | {'RSSI':5} | {'Variance':8} | {'Activity':8} | {'Last Seen':9}")
            print(f"  {'-'*12} | {'-'*15} | {'-'*5} | {'-'*8} | {'-'*8} | {'-'*9}")
            now = time.time()
            for nid, nd in sorted(active_nodes_data.items()):
                status = "ONLINE" if now - nd["last_seen"] < 2.5 else "STALE"
                elapsed = now - nd["last_seen"]
                print(f"  {nid:12} | {nd['ip']:15} | {nd['rssi']:4}d | {nd['variance']:8.4f} | {nd['level']:8} | {elapsed:4.1f}s ago ({status})")
                
        print("\n3D TARGET POSITION ESTIMATE:")
        if latest_position["active"]:
            print(f"  Raw:    x: {latest_position['x']:5.2f}m, y: {latest_position['y']:5.2f}m, z: {latest_position['z']:5.2f}m")
            print(f"  Smooth: x: {latest_position['x_smooth']:5.2f}m, y: {latest_position['y_smooth']:5.2f}m, z: {latest_position['z_smooth']:5.2f}m")
        else:
            print("  Offline (Need at least 3 active nodes to compute position)")
            
    print("=====================================================================")

def main():
    global running
    load_config()
    setup_csv_logger()
    
    # Start thread receivers
    recv_thread = threading.Thread(target=udp_receiver_thread, daemon=True)
    recv_thread.start()
    
    eng_thread = threading.Thread(target=processing_engine_thread, daemon=True)
    eng_thread.start()
    
    # Start web server
    httpd = start_http_server()
    
    # Wait for nodes to pop up and print stats
    time.sleep(1.0)
    
    try:
        # Check if terminal supports ANSI escaping
        supports_ansi = sys.platform != 'win32' or 'ANSICON' in os.environ or os.environ.get('TERM') == 'xterm'
        # Force ANSI escape codes support on newer windows consoles
        if sys.platform == 'win32':
            os.system('') # Enables VT100 code support in Windows Cmd/PowerShell
            supports_ansi = True
            
        while running:
            if supports_ansi:
                print_terminal_dashboard()
            else:
                # Fallback to simple logging
                with data_lock:
                    now = time.time()
                    online = [nid for nid, nd in active_nodes_data.items() if now - nd["last_seen"] < 2.5]
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Active nodes: {len(online)} | Position Active: {latest_position['active']}")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down Central Hub Server...")
    finally:
        running = False
        httpd.shutdown()
        if csv_file_handle:
            csv_file_handle.close()
        print("[INFO] Shutdown complete. Bye!")

if __name__ == "__main__":
    main()
