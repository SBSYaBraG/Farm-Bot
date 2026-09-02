/**
 * LimitSwitch.cpp - Multi-Axis Limit Switch Implementation
 * 
 * Handles limit detection and backoff for X, Y, Z axes
 */

#include "LimitSwitch.h"
#include "MotorControl.h"
#include "PositionManager.h"

static const uint8_t limitPins[4] = {
  0,              // AXIS_NONE
  X_LIMIT_PIN,    // AXIS_X
  Y_LIMIT_PIN,    // AXIS_Y
  Z_LIMIT_PIN     // AXIS_Z
};

static const bool homeDirections[4] = {
  false,              // AXIS_NONE
  X_HOME_DIRECTION,   // AXIS_X
  Y_HOME_DIRECTION,   // AXIS_Y
  Z_HOME_DIRECTION    // AXIS_Z
};

void initializeLimitSwitch() {
  pinMode(X_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Z_LIMIT_PIN, INPUT_PULLUP);
  Serial.println("Limit switches initialized");
}

bool checkLimitSwitch(Axis axis, bool direction) {
  if (axis < AXIS_X || axis > AXIS_Z) return false;
  
  if (digitalRead(limitPins[axis]) == LOW) {
    Serial.print("LIMIT SWITCH TRIGGERED on ");
    Serial.print((char)('X' + axis - 1));
    Serial.println("-axis!");
    
    if (direction == homeDirections[axis]) {
      // Hitting home position
      setCurrentPosition(axis, 0);
      Serial.println("Home position (0) set");
    } else {
      // Hitting far limit
      setMaxPosition(axis, getCurrentPosition(axis));
      Serial.print("Maximum position updated to: ");
      Serial.println(getMaxPosition(axis));
    }
    
    backOffFromLimit(axis, !direction);
    return true;
  }
  
  return false;
}

void backOffFromLimit(Axis axis, bool direction) {
  Serial.println("Backing off from limit...");
  
  setDirection(axis, direction);
  
  for (int i = 0; i < BACKOFF_STEPS; i++) {
    stepMotor(axis, MAX_STEP_DELAY, direction);
  }
  
  Serial.println("Backed off from limit");
}