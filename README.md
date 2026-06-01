# LUMOS RF — Advanced ESP8266 Wi-Fi Sensing & Motion Analysis Node

LUMOS RF is an experimental wireless sensing and telemetry platform that uses radio frequency (RF) signal disturbances to detect human presence, motion, and activity level. By monitoring and processing Received Signal Strength Indicator (RSSI) fluctuations, LUMOS RF demonstrates how wireless infrastructure (like a home Wi-Fi router) can double as a passive motion detection system.

---

### Dataset Notice

The datasets included in this repository were collected using:

Edimax 2.4 GHz Wi-Fi Router
ESP8266 NodeMCU Receiver
Indoor residential environment

Because Wi-Fi sensing depends heavily on room geometry, furniture placement, wall materials, antenna orientation, router characteristics, and RF noise conditions, the provided datasets may not directly generalize to other environments.

The datasets are intended as research and experimentation resources.

For my specific setup, the collected datasets achieved approximately 90% detection accuracy during testing. Results may vary significantly when reproduced using different routers, antennas, room layouts, or hardware platforms.

Users are encouraged to generate their own datasets using the included dataset generation tools for best performance in their environments.

---

## 📡 The Science of Wi-Fi Sensing

### 1. Multipath Propagation & Interference
In an indoor setting, radio waves do not just travel in a straight line from the transmitter (the Wi-Fi router) to the receiver (the NodeMCU). They bounce off walls, ceiling, furniture, and metallic surfaces. This creates a complex web of signal pathways called **multipath propagation**.

When these waves converge at the NodeMCU's antenna, they add together. Depending on their relative phases, they either reinforce each other (constructive interference) or cancel each other out (destructive interference). This forms a spatial "fading map" throughout the room.

```
       [ Edimax 3G-6200n Router (TX) ]
              /      |      \
             /       |       \   (Reflected path off wall)
            /        |        \
Direct Path/         |         \-----> [ Wall ]
          /    [Moving Body]                  \
         /           |                         \
        v            v                          v
             [ NodeMCU ESP8266 (RX) ]
```

### 2. The Human Body as an RF Obstacle
Human tissue consists of approximately 70% water. Liquid water has a high dielectric constant and absorbs and scatters electromagnetic radiation at $2.4\text{ GHz}$ (which is why microwave ovens use this frequency to heat food). 
When a person moves:
- They obstruct specific multipath wave components.
- The constructive/destructive phase balances shift.
- The **Received Signal Strength Indicator (RSSI)**—which represents the total bulk power of the combined multipath wavefronts—fluctuates in response.

### 3. Limitations of RSSI vs. CSI (Channel State Information)
* **RSSI** is a single, coarse scalar value representing the combined power of all incoming wave paths. It is easy to capture but lacks spatial awareness. A hand moving directly next to the antenna can register the exact same RSSI drop as a person walking in the background. It is also highly susceptible to external noise (Bluetooth, microwaves).
* **CSI** measures the amplitude and phase of *each individual carrier frequency* (subcarrier) within the Wi-Fi OFDM channel. This provides a fine-grained, high-dimensional frequency signature (a channel response matrix). It behaves like an "RF hologram" of the room, enabling advanced tasks like breathing detection, localization, and fine motion recognition.
* *Note: The ESP8266 does not natively support CSI extraction due to closed PHY firmware. The LUMOS RF architecture establishes the foundations of signal processing and dataset structures to make the platform ready for a future ESP32 CSI upgrade.*

---

## 🔌 Hardware Wiring & Pinouts

Wiring the SPI MicroSD Card module to the NodeMCU ESP8266 is straightforward. Ensure all connections are secure.

| SD Card Module Pin | NodeMCU Pin | ESP8266 GPIO Pin | Purpose |
| :--- | :--- | :--- | :--- |
| **VCC** | **3V3** | - | Power input (3.3V) |
| **GND** | **GND** | - | Common ground |
| **MISO** | **D6** | GPIO12 | Master In Slave Out (SPI Data) |
| **MOSI** | **D7** | GPIO13 | Master Out Slave In (SPI Data) |
| **SCK** | **D5** | GPIO14 | Serial Clock (SPI Clock) |
| **CS** | **D8** | GPIO15 | Chip Select (Default HSPI CS) |

> [!WARNING]
> **Boot Pin Safety Note**: On the ESP8266, pin `GPIO15` (D8) must be pulled LOW during boot for the microcontroller to enter the flash boot mode. Some cheap MicroSD modules have strong internal pull-ups on the CS pin. If your NodeMCU fails to boot or gets stuck in a bootloop when wired to the SD module, change the CS pin in `Config.h` to `D2` (GPIO4) or `D4` (GPIO2) and re-wire the CS line accordingly.

---

## 📂 Project Structure

```
e:\Kartik\LUMOS RF\
├── firmware\
│   └── LumosRF\
│       ├── LumosRF.ino             # Setup, calibration, and main sensor loop
│       ├── Config.h                # System, pin, logging, and threshold settings
│       ├── WifiManager.h           # WiFi connectivity and RSSI extraction
│       ├── WifiManager.cpp
│       ├── Filters.h               # Sliding buffers, variance, and baseline drift algorithms
│       ├── Filters.cpp
│       ├── SDLogger.h              # MicroSD logging and rolling log file management
│       ├── SDLogger.cpp
│       ├── MotionClassifier.h      # Anomaly scoring and motion intensity parsing
│       └── MotionClassifier.cpp
├── tools\
│   ├── live_plotter.py             # Python script for real-time serial plotting
│   ├── csv_analyzer.py             # Offline log analyzer, timeline, and spectrogram generator
│   └── dataset_generator.py        # CLI dataset acquisition tool for TinyML datasets
└── README.md                       # This file (documentation and instructions)
```

---

## 🛠️ Software Setup & Installation

### 1. Arduino IDE Setup (Firmware)
1. Open the Arduino IDE on your computer.
2. Add the ESP8266 Board Manager:
   * Go to **File > Preferences**.
   * Add the following URL to **Additional Boards Manager URLs**:
     `http://arduino.esp8266.com/stable/package_esp8266com_index.json`
   * Go to **Tools > Board > Boards Manager**, search for `esp8266`, and click **Install**.
3. Select your board:
   * Go to **Tools > Board > ESP8266 Boards** and select **NodeMCU 1.0 (ESP-12E Module)**.
4. Select the correct Port under **Tools > Port**.
5. Libraries needed:
   * The sketch uses standard built-in ESP8266 libraries (`ESP8266WiFi`, `SPI`, `SD`). No additional library installation is required.
6. Open `firmware/LumosRF/LumosRF.ino`.
7. Configure your SSID, password, and thresholds in `Config.h`.
8. Click **Upload** (Arrow icon).

### 2. Python Environment Setup (Analytics Tools)
The Python scripts require `pyserial`, `numpy`, and `matplotlib`. Install them using pip:

```bash
pip install pyserial numpy matplotlib
```

---

## 📈 Running the Python Analytics Utilities

### 1. Real-Time Telemetry Plotter (`live_plotter.py`)
This script connects to the ESP8266's serial port and draws a real-time, double-panel rolling graph. It isolates telemetry data and filters out text-based logs, printing them cleanly to the console.

* **Usage**:
  ```bash
  python tools/live_plotter.py --port COM3 --baud 115200
  ```
  *(Replace `COM3` with your board's serial port. On Linux/macOS, use `/dev/ttyUSB0` or similar).*

* **Visual Output**:
  * **Top Panel**: Displays raw RSSI and its smoothed moving average in real-time.
  * **Bottom Panel**: Displays sliding signal variance with colored horizontal threshold indicators.
  * **Status Bar**: A dynamic color-coded banner showing current activity: **IDLE** (Green), **SLIGHT** (Yellow), **MODERATE** (Orange), and **HEAVY** (Red).

### 2. Post-Run CSV Log Analyzer (`csv_analyzer.py`)
This tool processes logs saved to the MicroSD card (copy the CSV files from the SD card to your computer first). It draws a 4-panel historical summary, including a spectrogram.

* **Usage**:
  ```bash
  python tools/csv_analyzer.py path/to/lumos_001.csv
  ```

* **Dashboard Panels**:
  1. **Bulk RSSI Envelope**: Shows raw vs smoothed signal levels.
  2. **Signal Variance**: Highlights points of high disturbance.
  3. **Event Timeline**: Fills the background with color codes corresponding to classified event durations.
  4. **RF Fluctuation Spectrogram**: Computes and displays a 2D frequency heatmap of the RSSI variations. Moving speed corresponds directly to frequency height (Hz): slow walking lights up $0.5 - 1.5\text{ Hz}$, while rapid waving or jumping lights up $2.5 - 4.5\text{ Hz}$.

### 3. TinyML Dataset Generator (`dataset_generator.py`)
To train a machine learning model (e.g. Edge Impulse or scikit-learn) to recognize specific activities, you need labeled training data. This interactive command-line tool coordinates data capture sessions.

* **Usage**:
  ```bash
  python tools/dataset_generator.py --port COM3 --duration 30
  ```
1. Run the script. It will prompt you for the activity name (e.g., `sitting`, `walking`, `typing`).
2. A 3-second countdown will display. Get into position and perform the action.
3. The script records the data in real-time, displaying a progress bar and sample counts.
4. It exports a structured CSV file directly into the `datasets/` folder: `datasets/dataset_<label>_<timestamp>.csv`.
5. You can upload these files straight into TinyML tools to build classifiers.

---

## 🧪 Calibration & Optimization Tips

* **Quiet Calibration**: When powering up the system, make sure the room is completely empty/still for the first 10 seconds. This is critical for the system to establish a baseline noise floor. If calibration is done while moving, the system will adjust the noise floor too high, causing it to ignore actual motion later.
* **Sensitivity Tuning**: If you notice the system is triggering false alerts or missing movements:
  * Open `Config.h`.
  * Adjust `SLIGHT_THRESHOLD`, `MODERATE_THRESHOLD`, and `HEAVY_THRESHOLD`.
  * For example, lowering `SLIGHT_THRESHOLD` will make the system more sensitive to small movements, but might introduce false alarms from background RF noise.
* **Baseline Adaptation**: The Exponential Moving Average updates the baseline at a rate controlled by `BASELINE_ALPHA`. A small value (like `0.005`) ensures the system adapts to gradual temperature and weather changes without losing sensitivity to human presence.
