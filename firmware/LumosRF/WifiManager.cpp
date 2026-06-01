/**
 * @file WifiManager.cpp
 * @brief Implementation of Wi-Fi management routines.
 */

#include "WifiManager.h"

WifiManager::WifiManager() : 
    _lastReconnectAttempt(0), 
    _isConnecting(false) {
}

void WifiManager::begin() {
    Serial.println("[INFO] Initializing Wi-Fi module...");
    
    // Set WiFi to Station (client) mode
    WiFi.mode(WIFI_STA);
    
    // IMPORTANT FOR RF SENSING:
    // By default, the ESP8266 uses Modem-Sleep mode, turning off the RF circuit 
    // when not transmitting to save power. This creates massive artificial drops 
    // and fluctuations in RSSI, which ruins motion sensing. 
    // We disable sleep to keep the receiver radio fully powered and active.
    WiFi.setSleepMode(WIFI_NONE_SLEEP);
    
    Serial.print("[INFO] Connecting to AP: ");
    Serial.println(WIFI_SSID);
    
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    unsigned long startAttemptTime = millis();
    
    // Blocking wait for initial connection (with timeout)
    while (WiFi.status() != WL_CONNECTED && (millis() - startAttemptTime < WIFI_CONNECTION_TIMEOUT_MS)) {
        delay(500);
        Serial.print(".");
        // Blink built-in LED during connection attempt
        digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    }
    Serial.println();
    
    if (WiFi.status() == WL_CONNECTED) {
        digitalWrite(STATUS_LED_PIN, LOW); // Turn on LED (Active Low on NodeMCU) to indicate connected
        Serial.print("[INFO] WiFi Connected. IP Address: ");
        Serial.println(WiFi.localIP());
        Serial.print("[INFO] Signal Strength (RSSI): ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
    } else {
        digitalWrite(STATUS_LED_PIN, HIGH); // Turn off LED
        Serial.println("[WARN] WiFi Connection failed or timed out. Operating in disconnected sensing mode.");
        _isConnecting = true;
    }
}

bool WifiManager::isConnected() {
    return (WiFi.status() == WL_CONNECTED);
}

int8_t WifiManager::getRSSI() {
    if (!isConnected()) {
        // Return a sentinel value representing "no signal"
        return -127;
    }
    return WiFi.RSSI();
}

void WifiManager::keepAlive() {
    unsigned long currentMillis = millis();
    
    if (!isConnected()) {
        digitalWrite(STATUS_LED_PIN, HIGH); // Turn off LED if disconnected
        
        // Non-blocking reconnect attempt every 10 seconds
        if (currentMillis - _lastReconnectAttempt >= 10000) {
            _lastReconnectAttempt = currentMillis;
            Serial.println("[WARN] WiFi disconnected. Attempting reconnection...");
            
            // Re-initiate connection
            WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        }
    } else {
        // Keep LED ON when connected
        digitalWrite(STATUS_LED_PIN, LOW);
    }
}
