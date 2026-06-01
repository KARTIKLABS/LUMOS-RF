/**
 * @file Filters.cpp
 * @brief Implementation of signal processing filters.
 */

#include "Filters.h"
#include <math.h>

Filters::Filters() : 
    _head(0), 
    _count(0), 
    _isCalibrating(false), 
    _calibrationCount(0),
    _calibrationRSSIAccumulator(0.0),
    _calibrationVarAccumulator(0.0),
    _calibratedVarCount(0),
    _baselineRSSI(-60.0f),
    _noiseFloor(0.05f) {
    
    // Initialize circular buffer with zero
    for (int i = 0; i < WINDOW_SIZE; i++) {
        _buffer[i] = 0;
    }
}

void Filters::addSample(int8_t rssi) {
    _buffer[_head] = rssi;
    _head = (_head + 1) % WINDOW_SIZE;
    
    if (_count < WINDOW_SIZE) {
        _count++;
    }
}

bool Filters::isWindowFull() const {
    return (_count >= WINDOW_SIZE);
}

float Filters::getMean() const {
    if (_count == 0) return 0.0f;
    
    long sum = 0;
    for (int i = 0; i < _count; i++) {
        sum += _buffer[i];
    }
    return (float)sum / _count;
}

float Filters::getVariance() const {
    if (_count < 2) return 0.0f;
    
    float mean = getMean();
    double sumSqDiff = 0.0;
    
    for (int i = 0; i < _count; i++) {
        float diff = _buffer[i] - mean;
        sumSqDiff += (diff * diff);
    }
    
    // Sample variance (divided by N - 1)
    return (float)(sumSqDiff / (_count - 1));
}

void Filters::startCalibration() {
    _isCalibrating = true;
    _calibrationCount = 0;
    _calibrationRSSIAccumulator = 0.0;
    _calibrationVarAccumulator = 0.0;
    _calibratedVarCount = 0;
    _count = 0;
    _head = 0;
    Serial.println("[INFO] Calibration phase started. Please remain still near the system...");
}

bool Filters::isCalibrating() const {
    return _isCalibrating;
}

void Filters::processCalibrationSample(int8_t rssi) {
    if (!_isCalibrating) return;
    
    // Add raw RSSI to circular buffer
    addSample(rssi);
    
    _calibrationCount++;
    _calibrationRSSIAccumulator += rssi;
    
    // Once the buffer window is full, accumulate variance to determine noise floor
    if (isWindowFull()) {
        _calibrationVarAccumulator += getVariance();
        _calibratedVarCount++;
    }
    
    // Check if calibration period is complete
    if (_calibrationCount >= CALIBRATION_SAMPLES) {
        _isCalibrating = false;
        
        // Compute final calibration parameters
        _baselineRSSI = (float)(_calibrationRSSIAccumulator / _calibrationCount);
        
        if (_calibratedVarCount > 0) {
            _noiseFloor = (float)(_calibrationVarAccumulator / _calibratedVarCount);
        } else {
            _noiseFloor = 0.05f; // Fallback sensible default if variance couldn't be calculated
        }
        
        // Ensure noise floor is not zero to avoid division by zero later
        if (_noiseFloor < 0.001f) {
            _noiseFloor = 0.001f;
        }
        
        Serial.println("[INFO] Calibration complete!");
        Serial.print("[INFO] Calibrated Baseline RSSI: ");
        Serial.print(_baselineRSSI, 2);
        Serial.println(" dBm");
        Serial.print("[INFO] Calibrated Noise Floor (Variance): ");
        Serial.print(_noiseFloor, 4);
        Serial.println(" dBm^2");
    }
}

float Filters::getBaselineRSSI() const {
    return _baselineRSSI;
}

float Filters::getNoiseFloor() const {
    return _noiseFloor;
}

void Filters::adaptBaseline(float currentMean) {
    if (_isCalibrating) return;
    
    // EMA drift tracking: slowly updates baseline RSSI during idle periods.
    // This allows the system to follow slow long-term environmental drifts.
    _baselineRSSI = ((1.0f - BASELINE_ALPHA) * _baselineRSSI) + (BASELINE_ALPHA * currentMean);
}
