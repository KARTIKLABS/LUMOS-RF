# Guide to Running LUMOS RF 3D

This guide outlines how to configure, deploy, and run the **LUMOS RF 3D** passive spatial localization system.

---

## 🏗️ System Architecture Overview

The system consists of:
1. **ESP8266 Anchor Nodes**: Standard NodeMCUs placed at known coordinates in the room. They measure RSSI from the main WiFi router, calculate signal statistics, and stream JSON packets over UDP.
2. **Central Hub Server (`hub_server.py`)**: Runs on a central PC/Raspberry Pi. It aggregates UDP streams, runs the trilateration solver, smooths data with a Kalman Filter, and serves the Web Dashboard.
3. **3D Web Visualizer**: Hosted locally on port `8080`. It renders the room wireframe, anchors, and target paths in real-time WebGL using Three.js.

---

## 🛠️ Step-by-Step Setup

### Step 1: Install Python Dependencies
On the central computer running the hub server, open a terminal and install the required libraries:
```bash
pip install numpy scipy matplotlib pyserial
```

### Step 2: Configure & Flash ESP8266 Nodes
1. Open the Arduino IDE.
2. Open `firmware/LumosRF/LumosRF.ino`.
3. Open `Config.h` and update the connection settings:
   - Enter your Wi-Fi credentials (`WIFI_SSID` and `WIFI_PASSWORD`).
   - Assign a unique identifier to the node, e.g., `node_1`:
     ```cpp
     #define NODE_ID "node_1"
     ```
   - Update `UDP_HUB_IP` to the local IP address of your central computer running Python.
   - (Optional) Adjust the `UDP_HUB_PORT` if port `5001` is already in use.
4. Select the board (**NodeMCU 1.0 (ESP-12E Module)**) and click **Upload**.
5. Repeat this process for each node in your room, ensuring each has a unique `NODE_ID` (e.g. `node_2`, `node_3`, `node_4`).

### Step 3: Define Node Positions in the Room
Open `tools/config.json` and customize the physical coordinates of each node based on your room dimensions (in meters):
```json
"nodes": {
  "node_1": {
    "name": "Front Left Anchor",
    "x": 0.0,
    "y": 0.0,
    "z": 1.0
  },
  "node_2": {
    "name": "Front Right Anchor",
    "x": 5.0,
    "y": 0.0,
    "z": 1.0
  },
  "node_3": {
    "name": "Back Left Anchor",
    "x": 0.0,
    "y": 5.0,
    "z": 1.8
  },
  "node_4": {
    "name": "Back Right Anchor",
    "x": 5.0,
    "y": 5.0,
    "z": 1.8
  }
}
```
*Note: Make sure your `room_bounds` in `config.json` match your room size.*

### Step 4: Run the Central Hub Server
Start the aggregator on your central computer:
```bash
python tools/hub_server.py
```
This script will:
- Bind to UDP port `5001` to receive node packets.
- Launch the web server on `http://localhost:8080`.
- Print a real-time ASCII dashboard showing online anchors, current RSSI/variance values, and estimated target positions.

### Step 5: Launch the 3D Web UI
1. Open your web browser.
2. Navigate to: **`http://localhost:8080`**
3. You will see a live 3D room. 
   - **Green Spheres** are your ESP8266 anchors (they will turn orange/red when significant movement is detected near them).
   - **Central blue cylinder** represents the transmitter.
   - **Glowing orange sphere** is the calculated position of the human target, dragging a trail of their path behind them.

---

## 📈 Running the Command Line Tools in UDP Mode

You can also use the upgraded CLI tools to graph or capture data over Wi-Fi instead of Serial:

### Real-Time Single Node Plotter
To stream live RSSI and variance charts for a specific node:
```bash
python tools/live_plotter.py --mode udp --port 5001 --node node_1
```

### TinyML Dataset Capture
To record a training dataset from a wireless node over the network:
```bash
python tools/dataset_generator.py --mode udp --port 5001 --node node_1 --label walking --duration 45
```
This saves a clean dataset directly to the `datasets/` folder for machine learning classification.
