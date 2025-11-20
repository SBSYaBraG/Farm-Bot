/**
 * SystemOperations.cpp - Multi-Axis Homing Implementation
 * 
 * Enhanced homing for X, Y, Z axes - finds both home and far limits
 */

#include "SystemOperations.h"
#include "MotorControl.h"
#include "PositionManager.h"
#include "LimitSwitch.h"
#include "CommandProcessor.h"
#include "ALM_Monitor.h"

extern volatile bool emergencyStopTriggered;

static const bool homeDirections[4] = {
  false, X_HOME_DIRECTION, Y_HOME_DIRECTION, Z_HOME_DIRECTION
};

static const uint8_t limitPins[4] = {
  0, X_LIMIT_PIN, Y_LIMIT_PIN, Z_LIMIT_PIN
};

static const uint8_t pulPins[4] = {
  0, X_PUL_PIN, Y_PUL_PIN, Z_PUL_PIN
};

void runHoming(Axis axis) {
  if (axis < AXIS_X || axis > AXIS_Z) {
    Serial.println("ERROR: Invalid axis for homing");
    return;
  }
  
  char axisName = 'X' + axis - 1;
  
  Serial.print("\n===== HOMING ");
  Serial.print(axisName);
  Serial.println("-AXIS =====");
  
  emergencyStopTriggered = false;
  setSystemHomed(axis, false);
  
  enableMotor(axis);
  
  // STEP 1: Find home position
  Serial.println("STEP 1: Finding home position...");
  
  bool direction = homeDirections[axis];
  setDirection(axis, direction);
  
  long safety_counter = 0;
  
  while (digitalRead(limitPins[axis]) == HIGH) {
    if (safety_counter % 50 == 0) {
      monitorAllALM();
      if (checkForEmergencyStop() || isAnyALMCritical()) {
        Serial.println("Homing aborted by emergency");
        disableMotor(axis);
        return;
      }
    }
    
    digitalWrite(pulPins[axis], HIGH);
    delayMicroseconds(10);
    digitalWrite(pulPins[axis], LOW);
    delayMicroseconds(HOMING_STEP_DELAY - 10);
    
    updatePosition(axis, direction == CCW ? 1 : -1);
    
    safety_counter++;
    if (safety_counter > HOMING_TIMEOUT) {
      Serial.println("ERROR: Home limit not found");
      disableMotor(axis);
      return;
    }
  }
  
  Serial.println("Home limit found!");
  setCurrentPosition(axis, 0);
  backOffFromLimit(axis, !direction);
  
  if (emergencyStopTriggered || isAnyALMCritical()) {
    Serial.println("Homing aborted during backoff");
    disableMotor(axis);
    return;
  }
  
  // STEP 2: Find far position
  Serial.println("\nSTEP 2: Finding far position...");
  
  direction = !homeDirections[axis];
  setDirection(axis, direction);
  safety_counter = 0;
  
  while (digitalRead(limitPins[axis]) == HIGH) {
    if (safety_counter % 50 == 0) {
      monitorAllALM();
      if (checkForEmergencyStop() || isAnyALMCritical()) {
        Serial.println("Homing aborted by emergency");
        disableMotor(axis);
        return;
      }
    }
    
    digitalWrite(pulPins[axis], HIGH);
    delayMicroseconds(10);
    digitalWrite(pulPins[axis], LOW);
    delayMicroseconds(HOMING_STEP_DELAY - 10);
    
    updatePosition(axis, direction == CCW ? 1 : -1);
    
    safety_counter++;
    if (safety_counter > HOMING_TIMEOUT) {
      Serial.println("ERROR: Far limit not found");
      disableMotor(axis);
      return;
    }
  }
  
  Serial.println("Far limit found!");
  long maxPos = getCurrentPosition(axis);
  setMaxPosition(axis, maxPos);
  
  Serial.print("Total travel: ");
  Serial.print(maxPos);
  Serial.println(" steps");
  
  backOffFromLimit(axis, !direction);
  
  if (emergencyStopTriggered || isAnyALMCritical()) {
    Serial.println("Homing aborted during backoff");
    disableMotor(axis);
    return;
  }
  
  // STEP 3: Move to center
  Serial.println("\nSTEP 3: Moving to center...");
  
  long centerPos = maxPos / 2;
  long stepsToCenter = centerPos - getCurrentPosition(axis);
  bool centerDirection = (stepsToCenter > 0);
  
  if (stepsToCenter != 0) {
    setDirection(axis, centerDirection);
    bool success = moveSteps(axis, abs(stepsToCenter), centerDirection);
    
    if (!success) {
      Serial.println("Homing interrupted during centering");
      disableMotor(axis);
      return;
    }
  }
  
  setSystemHomed(axis, true);
  disableMotor(axis);
  
  Serial.print("\n===== ");
  Serial.print(axisName);
  Serial.println("-AXIS HOMING COMPLETE =====");
  Serial.print("Total travel: ");
  Serial.print(getMaxPosition(axis));
  Serial.println(" steps");
  Serial.print("Current position: ");
  Serial.print(getCurrentPosition(axis));
  Serial.print(" (");
  Serial.print(getPositionPercentage(axis));
  Serial.println("%)");
  Serial.println("System ready!\n");
}

void runHomingAll() {
  Serial.println("\n========== HOMING ALL AXES ==========");
  
  runHoming(AXIS_X);
  if (emergencyStopTriggered || isAnyALMCritical()) return;
  
  runHoming(AXIS_Y);
  if (emergencyStopTriggered || isAnyALMCritical()) return;
  
  runHoming(AXIS_Z);
  
  if (areAllAxesHomed()) {
    Serial.println("\n========== ALL AXES HOMED ==========");
    Serial.println("FarmBot ready for operation!");
  } else {
    Serial.println("\nWARNING: Not all axes homed successfully");
  }
}