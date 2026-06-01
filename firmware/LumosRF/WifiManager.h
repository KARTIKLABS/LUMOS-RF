/**
 * @file WifiManager.h
 * @brief Handles Wi-Fi connection establishment and telemetry data capture.
 */

#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <ESP8266WiFi.h>
#include "Config.h"

class WifiManager {
public:
    /**
     * @brief Construct a new Wifi Manager object
     */
    WifiManager();

    /**
     * @brief Initializes Wi-Fi hardware and initiates connection to the AP
     */
    void begin();

    /**
     * @brief Checks if the Wi-Fi connection is currently active
     * @return true if connected, false otherwise
     */
    bool isConnected();

    /**
     * @brief Retrieves the current RSSI (Received Signal Strength Indicator) from the AP
     * @return int8_t RSSI value in dBm, or -127 if not connected
     */
    int8_t getRSSI();

    /**
     * @brief Call inside loop() to handle auto-reconnection in the background
     */
    void keepAlive();

private:
    unsigned long _lastReconnectAttempt;
    bool _isConnecting;
};

#endif // WIFI_MANAGER_H
