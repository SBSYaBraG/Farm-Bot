/**
 * MotorControl.cpp - Multi-Axis Motor Control Implementation
 * 
 * Implements independent control for X, Y, Z axes with ALM monitoring
 */

#include "MotorControl.h"
#include "PositionManager.h"
#include "LimitSwitch.h"
#include "CommandProcessor.h"
#include "ALM_Monitor.h"

volatile bool emergencyStopTriggered = false;
static int stepCounter = 0;

// Axis pin configuration
struct AxisPins {
  uint8_t pulPin;
  uint8_t dirPin;
  uint8_t enaPin;
};

static const AxisPins axisPins[4] = {
  {0, 0, 0},                                  // AXIS_NONE
  {X_PUL_PIN, X_DIR_PIN, X_ENA_PIN},         // AXIS_X
  {Y_PUL_PIN, Y_DIR_PIN, Y_ENA_PIN},         // AXIS_Y
  {Z_PUL_PIN, Z_DIR_PIN, Z_ENA_PIN}          // AXIS_Z
};

void initializeMotor() {
  // X-axis
  pinMode(X_PUL_PIN, OUTPUT);
  pinMode(X_DIR_PIN, OUTPUT);
  pinMode(X_ENA_PIN, OUTPUT);
  digitalWrite(X_ENA_PIN, HIGH);
  
  // Y-axis
  pinMode(Y_PUL_PIN, OUTPUT);
  pinMode(Y_DIR_PIN, OUTPUT);
  pinMode(Y_ENA_PIN, OUTPUT);
  digitalWrite(Y_ENA_PIN, HIGH);
  
  // Z-axis
  pinMode(Z_PUL_PIN, OUTPUT);
  pinMode(Z_DIR_PIN, OUTPUT);
  pinMode(Z_ENA_PIN, OUTPUT);
  digitalWrite(Z_ENA_PIN, HIGH);
  
  initializeALM();
  
  Serial.println("Multi-axis motor control initialized");
  Serial.println("  X: 2 motors synchronized");
  Serial.println("  Y: 1 motor");
  Serial.println("  Z: 2 motors synchronized");
}

void enableMotor(Axis axis) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    digitalWrite(axisPins[axis].enaPin, LOW);
    delay(ENA_STABILIZATION_TIME);  // 200ms stabilization
  }
}

void disableMotor(Axis axis) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    digitalWrite(axisPins[axis].enaPin, HIGH);
  }
}

void disableAllMotors() {
  digitalWrite(X_ENA_PIN, HIGH);
  digitalWrite(Y_ENA_PIN, HIGH);
  digitalWrite(Z_ENA_PIN, HIGH);
}

void setDirection(Axis axis, bool direction) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    digitalWrite(axisPins[axis].dirPin, direction ? HIGH : LOW);
    delayMicroseconds(5);
  }
}

bool moveSteps(Axis axis, long stepsToMove, bool direction) {
  stepCounter = 0;
  setDirection(axis, direction);
  monitorAllALM();
  
  int stepDelay = MAX_STEP_DELAY;
  long totalSteps = stepsToMove;
  
  long accelerationSteps = totalSteps * 0.20;
  long decelerationSteps = totalSteps * 0.10;
  long constantSteps = totalSteps - accelerationSteps - decelerationSteps;
  
  if (accelerationSteps < 10) accelerationSteps = 10;
  if (decelerationSteps < 10) decelerationSteps = 10;
  
  if (accelerationSteps + decelerationSteps > totalSteps) {
    accelerationSteps = totalSteps / 2;
    decelerationSteps = totalSteps - accelerationSteps;
    constantSteps = 0;
  }

  Serial.println("Movement started - ALM monitoring active");

  // Acceleration
  for (long i = 0; i < accelerationSteps; i++) {
    stepCounter++;
    
    if (stepCounter >= EMERGENCY_CHECK_INTERVAL) {
      if (checkForEmergencyStop() || emergencyStopTriggered || isAnyALMCritical()) {
        Serial.print("Movement stopped during acceleration at: ");
        Serial.println(getCurrentPosition(axis));
        return false;
      }
      stepCounter = 0;
    }
    
    if (checkLimitSwitch(axis, direction)) return false;
    
    stepMotor(axis, stepDelay, direction);
    
    if (stepDelay > MIN_STEP_DELAY) {
      stepDelay -= ACCEL_RATE;
      if (stepDelay < MIN_STEP_DELAY) stepDelay = MIN_STEP_DELAY;
    }
  }

  // Constant speed
  for (long i = 0; i < constantSteps; i++) {
    stepCounter++;
    
    if (stepCounter >= EMERGENCY_CHECK_INTERVAL) {
      if (checkForEmergencyStop() || emergencyStopTriggered || isAnyALMCritical()) {
        Serial.print("Movement stopped during constant speed at: ");
        Serial.println(getCurrentPosition(axis));
        return false;
      }
      stepCounter = 0;
    }
    
    if (checkLimitSwitch(axis, direction)) return false;
    stepMotor(axis, stepDelay, direction);
  }

  // Deceleration
  for (long i = 0; i < decelerationSteps; i++) {
    stepCounter++;
    
    if (stepCounter >= EMERGENCY_CHECK_INTERVAL) {
      if (checkForEmergencyStop() || emergencyStopTriggered || isAnyALMCritical()) {
        Serial.print("Movement stopped during deceleration at: ");
        Serial.println(getCurrentPosition(axis));
        return false;
      }
      stepCounter = 0;
    }
    
    if (checkLimitSwitch(axis, direction)) return false;
    
    stepMotor(axis, stepDelay, direction);
    
    if (stepDelay < MAX_STEP_DELAY) {
      stepDelay += DECEL_RATE;
      if (stepDelay > MAX_STEP_DELAY) stepDelay = MAX_STEP_DELAY;
    }
  }
  
  Serial.println("Movement completed successfully");
  return true;
}

void stepMotor(Axis axis, int delayTime, bool direction) {
  monitorAllALM();
  
  if (axis < AXIS_X || axis > AXIS_Z) return;
  
  uint8_t pulPin = axisPins[axis].pulPin;
  
  digitalWrite(pulPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(pulPin, LOW);
  
  unsigned long stepStart = micros();
  unsigned long stepDelay = delayTime - 10;
  
  while ((micros() - stepStart) < stepDelay) {
    if ((micros() - stepStart) % 1000 < 50) {
      monitorAllALM();
    }
    delayMicroseconds(50);
  }
  
  updatePosition(axis, direction ? 1 : -1);
}

void emergencyStop() {
  emergencyStopTriggered = true;
  disableAllMotors();
  Serial.println("\nEMERGENCY STOP ACTIVATED");
  Serial.println("All motors disabled");
  Serial.println("Send 'S0' to resume");
}

void resumeOperations() {
  if (emergencyStopTriggered || isAnyALMCritical()) {
    emergencyStopTriggered = false;
    clearAllALM();
    Serial.println("Emergency stop cleared - operations resumed");
  } else {
    Serial.println("No emergency stop active");
  }
}

void processRelativeMove(Axis axis, long steps) {
  if (emergencyStopTriggered || isAnyALMCritical()) {
    Serial.println("Cannot move - emergency stop or ALM alarm active. Send 'S0' to resume.");
    return;
  }
  
  if (!isSystemHomed(axis)) {
    Serial.println("Axis must be homed before movement. Send 'H' to home.");
    return;
  }
  
  if (steps == 0) {
    Serial.println("Zero steps requested - no movement needed");
    return;
  }
  
  Serial.print("Relative move requested on axis ");
  Serial.print((char)('X' + axis - 1));
  Serial.print(": ");
  Serial.println(steps);
  
  long currentPos = getCurrentPosition(axis);
  long targetPosition = currentPos + steps;
  
  if (targetPosition < BACKOFF_STEPS) {
    Serial.println("WARNING: Movement limited to safe distance from home");
    targetPosition = BACKOFF_STEPS;
    steps = targetPosition - currentPos;
  } 
  else if (targetPosition > (getMaxPosition(axis) - BACKOFF_STEPS)) {
    Serial.println("WARNING: Movement limited to safe distance from maximum");
    targetPosition = getMaxPosition(axis) - BACKOFF_STEPS;
    steps = targetPosition - currentPos;
  }
  
  if (steps == 0) {
    Serial.println("Already at safe limit - no movement possible");
    return;
  }
  
  bool direction = (steps > 0);
  Serial.print("Direction: ");
  Serial.println(direction ? "CCW (forward)" : "CW (backward)");
  
  enableMotor(axis);
  bool success = moveSteps(axis, abs(steps), direction);
  
  if (!emergencyStopTriggered && !isAnyALMCritical()) {
    disableMotor(axis);
  }
  
  if (success && !emergencyStopTriggered && !isAnyALMCritical()) {
    Serial.print("Move complete. Position: ");
    Serial.print(getCurrentPosition(axis));
    Serial.print(" (");
    Serial.print(getPositionPercentage(axis));
    Serial.println("%)");
  }
}

void processAbsoluteMove(Axis axis, int percentage) {
  if (emergencyStopTriggered || isAnyALMCritical()) {
    Serial.println("Cannot move - emergency stop or ALM alarm active. Send 'S0' to resume.");
    return;
  }
  
  if (!isSystemHomed(axis)) {
    Serial.println("Axis must be homed before absolute positioning. Send 'H' to home.");
    return;
  }
  
  if (percentage != 25 && percentage != 50 && percentage != 75) {
    Serial.println("Invalid percentage. Only 25%, 50%, and 75% are supported.");
    return;
  }
  
  long maxPos = getMaxPosition(axis);
  if (maxPos <= 0) {
    Serial.println("Maximum position not set. Run homing first.");
    return;
  }
  
  long targetPosition = (maxPos * percentage) / 100;
  long currentPos = getCurrentPosition(axis);
  long steps = targetPosition - currentPos;
  
  Serial.print("Absolute move to ");
  Serial.print(percentage);
  Serial.print("% position (");
  Serial.print(targetPosition);
  Serial.println(" steps)");
  
  if (steps == 0) {
    Serial.println("Already at target position");
    return;
  }
  
  if (targetPosition < BACKOFF_STEPS || targetPosition > (maxPos - BACKOFF_STEPS)) {
    Serial.println("Target position too close to limits - move cancelled for safety");
    return;
  }
  
  bool direction = (steps > 0);
  Serial.print("Direction: ");
  Serial.println(direction ? "CCW (forward)" : "CW (backward)");
  
  enableMotor(axis);
  bool success = moveSteps(axis, abs(steps), direction);
  
  if (!emergencyStopTriggered && !isAnyALMCritical()) {
    disableMotor(axis);
  }
  
  if (success && !emergencyStopTriggered && !isAnyALMCritical()) {
    Serial.print("Absolute move complete. Position: ");
    Serial.print(getCurrentPosition(axis));
    Serial.print(" (");
    Serial.print(getPositionPercentage(axis));
    Serial.println("%)");
  }
}

bool isEmergencyStopActive() {
  return emergencyStopTriggered || isAnyALMCritical();
}