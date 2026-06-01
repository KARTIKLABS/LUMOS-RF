/**
 * @file Filters.h
 * @brief Header for signal processing filters, including moving averages, 
 *        sliding variance, calibration routines, and adaptive baseline tracking.
 */

#ifndef FILTERS_H
#define FILTERS_H

#include <Arduino.h>
#include "Config.h"

class Filters {
public:
    /**
     * @brief Construct a new Filters object
     */
    Filters();

    /**
     * @brief Adds a new RSSI sample to the sliding window circular buffer
     * @param rssi The raw RSSI sample
     */
    void addSample(int8_t rssi);

    /**
     * @brief Checks if the sliding window is fully populated
     * @return true if the window is full, false otherwise
     */
    bool isWindowFull() const;

    /**
     * @brief Computes the Simple Moving Average (SMA) of the current window
     * @return float The average RSSI
     */
    float getMean() const;

    /**
     * @brief Computes the sample variance of the current window
     * @return float The RSSI variance in dBm^2
     */
    float getVariance() const;

    /**
     * @brief Initiates the calibration sequence
     */
    void startCalibration();

    /**
     * @brief Checks if the system is currently calibrating
     * @return true if calibrating, false if complete
     */
    bool isCalibrating() const;

    /**
     * @brief Process a sample during the calibration phase
     * @param rssi The raw RSSI sample
     */
    void processCalibrationSample(int8_t rssi);

    /**
     * @brief Retrieves the calibrated baseline RSSI
     * @return float Baseline RSSI in dBm
     */
    float getBaselineRSSI() const;

    /**
     * @brief Retrieves the baseline noise floor (average idle variance)
     * @return float Noise floor variance in dBm^2
     */
    float getNoiseFloor() const;

    /**
     * @brief Gradually adapts the baseline RSSI to ambient drift (temperature, etc.)
     * @param currentMean The current SMA RSSI
     */
    void adaptBaseline(float currentMean);

private:
    // Circular Buffer for Sliding Window
    int8_t _buffer[WINDOW_SIZE];
    int _head;
    int _count;

    // Calibration Variables
    bool _isCalibrating;
    int _calibrationCount;
    
    // Accumulators for baseline calculation
    double _calibrationRSSIAccumulator;
    double _calibrationVarAccumulator;
    int _calibratedVarCount;

    // Calibrated References
    float _baselineRSSI;
    float _noiseFloor;
};

#endif // FILTERS_H
