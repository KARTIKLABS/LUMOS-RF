/**
 * @file Config.h
 * @brief Configuration constants for the LUMOS RF sensing system.
 * 
 * Contains all user-configurable parameters including WiFi credentials, 
 * hardware pins, signal processing constants, and SD logger configurations.
 */

#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ============================================================================
// SYSTEM & SERIAL SETTINGS
// ============================================================================
#define SERIAL_BAUD_RATE 115200

// ============================================================================
// WI-FI SETTINGS
// ============================================================================
// Replace with the credentials of your Edimax 3G-6200n Wi-Fi router
#define WIFI_SSID     "default"
#define WIFI_PASSWORD "12345678"
#define WIFI_CONNECTION_TIMEOUT_MS 20000 // 20 seconds timeout for boot connection

// ============================================================================
// HARDWARE PINOUTS (NodeMCU ESP8266)
// ============================================================================
// LED indicators for visual telemetry
#define STATUS_LED_PIN LED_BUILTIN // ESP8266 Built-in LED (GPIO2/D4, active LOW)

// ============================================================================
// SENSING & SIGNAL PROCESSING SETTINGS
// ============================================================================
#define SAMPLING_RATE_HZ 10                               // 10 readings per second
#define MEASUREMENT_INTERVAL_MS (1000 / SAMPLING_RATE_HZ) // Interval in ms (100 ms)

#define WINDOW_SIZE 20            // Number of samples in the rolling window (2 seconds)
#define CALIBRATION_SAMPLES 100   // Number of samples for baseline calibration (10 seconds)

// Variance threshold values for motion intensity classification.
// These are RSSI variance levels (dBm^2) derived from empirical testing.
#define SLIGHT_THRESHOLD   0.15f  // Threshold between IDLE and SLIGHT movement
#define MODERATE_THRESHOLD 1.20f  // Threshold between SLIGHT and MODERATE movement
#define HEAVY_THRESHOLD    4.50f  // Threshold between MODERATE and HEAVY movement

// Exponential Moving Average coefficient (alpha) for the baseline RSSI tracker.
// Determines how fast the baseline adapts to slow ambient drift (e.g., thermal fluctuations).
// Value between 0.0 and 1.0. A smaller value means slower adaptation.
#define BASELINE_ALPHA 0.005f

// ============================================================================
// UDP STREAMING SETTINGS
// ============================================================================
#define NODE_ID "node_1"               // Unique node ID for this receiver node
#define UDP_HUB_IP "192.168.1.100"     // IP address of the central hub running Python server
#define UDP_HUB_PORT 5001              // Port number of the central hub

#endif // CONFIG_H
