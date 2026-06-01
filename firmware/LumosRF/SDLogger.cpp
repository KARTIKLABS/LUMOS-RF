/**
 * @file SDLogger.cpp
 * @brief Implementation of the SD logging class.
 */

#include "SDLogger.h"

SDLogger::SDLogger() : 
    _initialized(false), 
    _currentFileIndex(1) {
    _currentFilename[0] = '\0';
}

bool SDLogger::begin() {
    Serial.println("[INFO] Initializing SD Card module...");
    
    // Initialize standard SPI SD card library.
    // D8 (GPIO15) is CS on the NodeMCU, which must be set to output.
    pinMode(SD_CS_PIN, OUTPUT);
    
    if (!SD.begin(SD_CS_PIN)) {
        Serial.println("[ERROR] SD card initialization failed!");
        Serial.println("[ERROR] Verify hardware wiring: VCC->3V3, GND->GND, MISO->D6, MOSI->D7, SCK->D5, CS->D8");
        _initialized = false;
        return false;
    }
    
    Serial.println("[INFO] SD card initialized successfully.");
    
    // Find and prepare the next available log file index
    if (findNextFile()) {
        if (createNewFile()) {
            _initialized = true;
            return true;
        }
    }
    
    _initialized = false;
    return false;
}

bool SDLogger::findNextFile() {
    char tempFilename[32];
    
    // Scan from 1 to 999 to find the first unused filename index
    for (int i = 1; i <= 999; i++) {
        snprintf(tempFilename, sizeof(tempFilename), "%s%03d%s", LOG_FILE_PREFIX, i, LOG_FILE_EXT);
        
        if (!SD.exists(tempFilename)) {
            _currentFileIndex = i;
            strncpy(_currentFilename, tempFilename, sizeof(_currentFilename));
            return true;
        }
    }
    
    Serial.println("[WARN] All log filenames (001-999) are exhausted! Overwriting index 999.");
    snprintf(_currentFilename, sizeof(_currentFilename), "%s999%s", LOG_FILE_PREFIX, LOG_FILE_EXT);
    _currentFileIndex = 999;
    return true;
}

bool SDLogger::createNewFile() {
    // Open in write mode, which creates the file if it does not exist
    File logFile = SD.open(_currentFilename, FILE_WRITE);
    
    if (logFile) {
        // Write the CSV column header
        logFile.println("timestamp,rssi,variance,event");
        logFile.close();
        
        Serial.print("[INFO] Active logging session opened: ");
        Serial.println(_currentFilename);
        return true;
    } else {
        Serial.print("[ERROR] Failed to create log file: ");
        Serial.println(_currentFilename);
        return false;
    }
}

bool SDLogger::logData(unsigned long timestamp, int8_t rssi, float variance, const char* eventStr) {
    if (!_initialized) {
        return false;
    }
    
    // Open file. In standard SD library, opening FILE_WRITE seeks to the end.
    File logFile = SD.open(_currentFilename, FILE_WRITE);
    
    if (logFile) {
        // Print CSV fields
        logFile.print(timestamp);
        logFile.print(",");
        logFile.print(rssi);
        logFile.print(",");
        logFile.print(variance, 4);
        logFile.print(",");
        logFile.println(eventStr);
        
        // Check size of the file to determine if we should roll over
        unsigned long fileSize = logFile.size();
        logFile.close(); // Close file immediately to flush data and ensure write integrity
        
        if (fileSize >= MAX_FILE_SIZE_BYTES) {
            Serial.print("[INFO] Log file ");
            Serial.print(_currentFilename);
            Serial.print(" reached size limit (");
            Serial.print(fileSize);
            Serial.println(" bytes). Rolling file...");
            
            // Increment file index
            if (findNextFile()) {
                createNewFile();
            }
        }
        
        return true;
    } else {
        // Log error on serial but don't crash
        Serial.print("[ERROR] Failed to write data line to file: ");
        Serial.println(_currentFilename);
        return false;
    }
}

bool SDLogger::isEnabled() const {
    return _initialized;
}

const char* SDLogger::getCurrentFilename() const {
    return _currentFilename;
}
