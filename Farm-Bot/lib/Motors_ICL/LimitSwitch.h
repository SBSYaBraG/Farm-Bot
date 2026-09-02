/**
 * LimitSwitch.h - Multi-Axis Limit Switch Detection
 * 
 * Handles limit switch detection for X, Y, and Z axes
 */

#ifndef LIMIT_SWITCH_H
#define LIMIT_SWITCH_H

#include <Arduino.h>
#include "Config.h"

void initializeLimitSwitch();
bool checkLimitSwitch(Axis axis, bool direction);
void backOffFromLimit(Axis axis, bool direction);

#endif // LIMIT_SWITCH_H