/**
 * @file MotionClassifier.h
 * @brief Classifies signal disturbances into motion intensity levels and 
 *        calculates anomaly scores.
 */

#ifndef MOTION_CLASSIFIER_H
#define MOTION_CLASSIFIER_H

#include <Arduino.h>
#include "Config.h"

// Enum representing the parsed motion levels
enum MotionLevel {
    LEVEL_IDLE = 0,
    LEVEL_SLIGHT,
    LEVEL_MODERATE,
    LEVEL_HEAVY
};

class MotionClassifier {
public:
    /**
     * @brief Construct a new Motion Classifier object
     */
    MotionClassifier();

    /**
     * @brief Calculates the anomaly score based on current variance and noise floor
     * @param variance Current sliding window variance
     * @param noiseFloor Calibrated noise floor variance
     * @return float The ratio of variance to noise floor
     */
    float calculateAnomalyScore(float variance, float noiseFloor) const;

    /**
     * @brief Classifies the movement intensity level based on the current variance
     * @param variance Current sliding window variance
     * @return MotionLevel The classified motion level
     */
    MotionLevel classify(float variance) const;

    /**
     * @brief Utility function to convert a MotionLevel enum to its string representation
     * @param level The MotionLevel enum
     * @return const char* String representation (e.g. "IDLE", "SLIGHT", etc.)
     */
    static const char* toString(MotionLevel level);
};

#endif // MOTION_CLASSIFIER_H
