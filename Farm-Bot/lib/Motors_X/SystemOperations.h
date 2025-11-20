/**
 * SystemOperations.h - Multi-Axis System Operations
 * 
 * Handles homing sequences for X, Y, and Z axes
 */

#ifndef SYSTEM_OPERATIONS_H
#define SYSTEM_OPERATIONS_H

#include <Arduino.h>
#include "Config.h"

void runHoming(Axis axis);
void runHomingAll();

#endif // SYSTEM_OPERATIONS_H