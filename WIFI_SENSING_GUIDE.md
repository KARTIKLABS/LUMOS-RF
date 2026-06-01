# LUMOS RF — Wi-Fi Sensing & TinyML Reference Guide

This guide compiles the research findings, physical principles, and machine learning insights discovered during the development and testing of the **LUMOS RF** Wi-Fi sensing node.

---

## 1. Physical Fundamentals of Wi-Fi Sensing

Wi-Fi sensing operates on the principle of **Multipath Propagation**. When a Wi-Fi transmitter (router) sends signals to a receiver (ESP8266), the radio waves do not travel in a single straight line. Instead, they bounce off walls, furniture, ceilings, and people.

* **Constructive & Destructive Interference:** The receiver sums all incoming waves. If you stand still, the sum remains constant. 
* **Dynamic Disturbance:** When a person walks or moves, they intercept and scatter the waves, causing the phases of the waves to shift. This results in rapid fluctuations in the received signal strength (**RSSI**).

---

## 2. Environmental & Electrical Disturbances

### A. Ceiling Fans: Why do they affect the graph?
A spinning ceiling fan acts as a continuous moving reflector. Its impact follows three distinct phases:
1. **Startup Phase (Inrush Current / EMI):** When first switched on, the fan's motor draws a massive initial current. This sudden current flow creates a temporary **Electromagnetic Interference (EMI)** field around the wall wires, degrading the Wi-Fi signal and generating high variance.
2. **Speed Transition:** As the blades slowly speed up, they intercept the signal path at a rate that our $10\text{ Hz}$ sampling rate can capture, showing up as "Moderate/Slight Motion".
3. **Full Speed Stabilization (Aliasing):** Once the fan reaches full speed, the blades move faster than our $100\text{ ms}$ sampling interval. Under the Nyquist theorem, this high-frequency motion cannot be resolved by the sampler, so it "aliases" and averages out, allowing the signal variance to settle back to the **IDLE** baseline.

### B. Do electrical wires in the walls disturb Wi-Fi?
* **Steady AC Current:** Standard electricity flowing through wires at $50/60\text{ Hz}$ has a very short wavelength and generates a stable magnetic field that does **not** interfere with the $2.4\text{ GHz}$ Wi-Fi frequencies directly.
* **Transient Spikes (Turn-on/off events):** Turning on high-power appliances (fans, refrigerators, vacuum cleaners) creates short electrical arcs and magnetic transients. These transients can cause brief packet drops, which register as instant RSSI spikes.

---

## 3. TinyML Classifier Design & Optimization

### A. The Sliding Window Approach
* **Single-Frame Classification (Inaccurate):** If you classify based on a single $100\text{ ms}$ data point, any instantaneous noise or momentary pause will trigger a false prediction.
* **Rolling Temporal Window (Accurate):** By grouping data into a sliding window of **15 samples (1.5 seconds)**, we compute smoothed features that represent the *overall behavior* rather than a single instant.

### B. Feature Engineering Checklist
To train the Random Forest model, we extract four robust features from the rolling window:
1. **`rolling_var_mean`**: The average variance of the window (filters out brief pauses).
2. **`rolling_var_max`**: The peak variance (captures sudden, energetic movements).
3. **`rolling_dev_mean`**: The average absolute deviation of RSSI from the moving average.
4. **`rolling_rssi_amp`**: The peak-to-peak amplitude (maximum RSSI minus minimum RSSI inside the window).

### C. Overcoming Label Noise
When recording a "walking" or "waving" session, you naturally pause or stand still occasionally. Because the generator labels the entire session as moving, the training data gets contaminated with "stillness" periods labeled as "walking."
* **Solution:** We filter the training dataset to skip any moving window whose average variance is lower than the stillness threshold ($< 0.15$). This forces the model to learn clean decision boundaries, jumping classification accuracy from **$62\%$ to $89\%+$**.

---

## 4. Best Practices for Training the Model

1. **Continuous Action:** Perform the activity consistently for the entire 30 seconds of recording.
2. **Fixed Hardware:** Tape or secure the router and ESP8266. If either device wobbles, the baseline changes and you must retrain.
3. **Active Zone:** Ensure the activity happens directly in the Line-of-Sight (LoS) path between the two devices for maximum signal contrast.
4. **Calibrate Quietly:** Stand outside the active zone during the initial 10-second calibration phase.
