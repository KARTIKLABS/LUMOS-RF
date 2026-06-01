/**
 * @file SDLogger.h
 * @brief Interfaces with the SPI MicroSD card module, managing sequential CSV logging 
 *        and rolling file sizes.
 */

#ifndef SD_LOGGER_H
#define SD_LOGGER_H

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include "Config.h"

class SDLogger {
public:
    /**
     * @brief Construct a new SDLogger object
     */
    SDLogger();

    /**
     * @brief Initializes SPI and the SD Card module.
     * @return true if initialization succeeded, false otherwise
     */
    bool begin();

    /**
     * @brief Logs a single row of telemetry to the active CSV file.
     *        Automatically handles file creation and file-rolling boundaries.
     * @param timestamp System timestamp in milliseconds since boot
     * @param rssi Current smoothed RSSI value
     * @param variance Current signal variance
     * @param eventStr Event string classification (e.g. "IDLE", "SLIGHT", etc.)
     * @return true if write succeeded, false if logging is disabled or failed
     */
    bool logData(unsigned long timestamp, int8_t rssi, float variance, const char* eventStr);

    /**
     * @brief Check if the SD logging is fully initialized and operational
     * @return true if active, false otherwise
     */
    bool isEnabled() const;

    /**
     * @brief Get the active log file path
     * @return const char* Active file name
     */
    const char* getCurrentFilename() const;

private:
    bool _initialized;
    char _currentFilename[32];
    int _currentFileIndex;

    /**
     * @brief Scans the SD card to find the next unused filename index
     */
    bool findNextFile();

    /**
     * @brief Creates a new file at _currentFilename and writes the CSV headers.
     * @return true if creation succeeded, false otherwise
     */
    bool createNewFile();
};

#endif // SD_LOGGER_H
