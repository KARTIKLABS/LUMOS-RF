/**
 * @file MotionClassifier.cpp
 * @brief Implementation of the motion classification system.
 */

#include "MotionClassifier.h"

MotionClassifier::MotionClassifier() {
}

float MotionClassifier::calculateAnomalyScore(float variance, float noiseFloor) const {
    if (noiseFloor <= 0.0001f) {
        return 0.0f;
    }
    // The anomaly score represents the multiple of the current variance 
    // compared to the calibrated resting noise floor.
    float score = variance / noiseFloor;
    return score;
}

MotionLevel MotionClassifier::classify(float variance) const {
    if (variance < SLIGHT_THRESHOLD) {
        return LEVEL_IDLE;
    } else if (variance < MODERATE_THRESHOLD) {
        return LEVEL_SLIGHT;
    } else if (variance < HEAVY_THRESHOLD) {
        return LEVEL_MODERATE;
    } else {
        return LEVEL_HEAVY;
    }
}

const char* MotionClassifier::toString(MotionLevel level) {
    switch (level) {
        case LEVEL_IDLE:
            return "IDLE";
        case LEVEL_SLIGHT:
            return "SLIGHT";
        case LEVEL_MODERATE:
            return "MODERATE";
        case LEVEL_HEAVY:
            return "HEAVY";
        default:
            return "UNKNOWN";
    }
}
