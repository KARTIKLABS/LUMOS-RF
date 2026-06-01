/**
 * @file LumosRF.ino
 * @brief LUMOS RF - Advanced ESP8266 Wi-Fi Sensing & Motion Analysis Node.
 * 
 * This is the main firmware entry point. It sets up hardware peripherals, 
 * performs baseline calibration, runs the signal processing loop, and
 * outputs telemetry over serial and writes to the SPI MicroSD card.
 */

#include "Config.h"
#include "WifiManager.h"
#include "Filters.h"
#include "MotionClassifier.h"
#include "SDLogger.h"

// System Components
WifiManager wifi;
Filters filter;
MotionClassifier classifier;
#if ENABLE_SD_LOGGING
SDLogger sdLogger;
#endif

// Timers and State Variables
unsigned long lastSampleTime = 0;
bool isCalibrated = false;
MotionLevel lastMotionLevel = LEVEL_IDLE;

void setup() {
    // Initialize Serial Port
    Serial.begin(SERIAL_BAUD_RATE);
    delay(1000); // Wait for serial monitor to open
    
    Serial.println("\n---");
    Serial.println("[BOOT] LUMOS RF Starting...");
    Serial.println("[BOOT] Advanced ESP8266 Wi-Fi Sensing Node");
    Serial.println("[BOOT] Designed for motion analysis & occupancy detection");
    Serial.println("---");
    
    // Initialize status indicator LED (Built-in)
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, HIGH); // Off initially (Active Low)
    
    // 1. Initialize WiFi connection to the Edimax router
    wifi.begin();
    
    // 2. Initialize SPI SD Card logging
#if ENABLE_SD_LOGGING
    if (!sdLogger.begin()) {
        Serial.println("[WARN] Logging disabled due to SD initialization failure. Serial telemetry active.");
    }
#endif
    
    // 3. Initiate Baseline Calibration
    // The user should remain still during this phase to establish the noise floor.
    filter.startCalibration();
}

void loop() {
    // Keep WiFi active and handle reconnection in the background
    wifi.keepAlive();
    
    unsigned long currentMillis = millis();
    
    // Non-blocking sampling timer
    if (currentMillis - lastSampleTime >= MEASUREMENT_INTERVAL_MS) {
        lastSampleTime = currentMillis;
        
        // Retrieve current RSSI from the router connection
        int8_t rawRssi = wifi.getRSSI();
        
        // Handle Calibration Phase
        if (filter.isCalibrating()) {
            filter.processCalibrationSample(rawRssi);
            
            // Print progress indicator
            if (millis() % 1000 < MEASUREMENT_INTERVAL_MS) {
                Serial.print("[INFO] Calibrating baseline... (Raw RSSI: ");
                Serial.print(rawRssi);
                Serial.println(" dBm)");
            }
            
            // Detect when calibration completes
            if (!filter.isCalibrating()) {
                isCalibrated = true;
                Serial.println("[INFO] System entered SENSING mode.");
                Serial.print("[INFO] Baseline RSSI: ");
                Serial.print((int)filter.getBaselineRSSI());
                Serial.println(" dBm");
            }
        }
        // Handle Active Sensing Mode
        else if (isCalibrated) {
            // Push sample into sliding window buffer
            filter.addSample(rawRssi);
            
            if (filter.isWindowFull()) {
                float rssiMean = filter.getMean();
                float rssiVar = filter.getVariance();
                float noiseFloor = filter.getNoiseFloor();
                float baselineRSSI = filter.getBaselineRSSI();
                
                // Compute disturbance metrics
                float anomalyScore = classifier.calculateAnomalyScore(rssiVar, noiseFloor);
                MotionLevel currentLevel = classifier.classify(rssiVar);
                const char* levelStr = MotionClassifier::toString(currentLevel);
                
                // ADAPTIVE BASELINE TRACKING:
                // Only adapt baseline RSSI when the room is IDLE (no movement).
                // If we adapt during movement, the large variance will pollute the 
                // baseline envelope, leading to desensitization.
                if (currentLevel == LEVEL_IDLE) {
                    filter.adaptBaseline(rssiMean);
                }
                
                // 1. Output Standard Structured Serial Data
                // The format is structured for ease of regex parsing by the Python plotter
                Serial.print("[DATA] RSSI: ");
                Serial.print(rawRssi);
                Serial.print(" | Mean: ");
                Serial.print(rssiMean, 2);
                Serial.print(" | Var: ");
                Serial.print(rssiVar, 4);
                Serial.print(" | Anomaly: ");
                Serial.print(anomalyScore, 2);
                Serial.print(" | Level: ");
                Serial.println(levelStr);
                
                // 2. Trigger Alerts for Motion Intensity Transitions
                // Alerts are triggered when transitioning from IDLE to any motion level,
                // or when motion intensity increases.
                if (currentLevel != LEVEL_IDLE && currentLevel != lastMotionLevel) {
                    Serial.print("[ALERT] Motion Detected: ");
                    Serial.println(levelStr);
                }
                
                // 3. Log to MicroSD Card (if module is active)
#if ENABLE_SD_LOGGING
                if (sdLogger.isEnabled()) {
                    bool writeSuccess = sdLogger.logData(currentMillis, rawRssi, rssiVar, levelStr);
                    if (!writeSuccess) {
                        Serial.println("[ERROR] SD card write failure!");
                    }
                }
#endif
                
                // Update historical state
                lastMotionLevel = currentLevel;
            }
        }
    }
}
