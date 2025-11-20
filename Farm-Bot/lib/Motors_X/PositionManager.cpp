/**
 * PositionManager.cpp - Multi-Axis Position Tracking Implementation
 * 
 * Manages position and state for 3 axes and ALM for 5 motors
 */

#include "PositionManager.h"

// Position tracking per axis
static long currentPosition[4] = {0, 0, 0, 0};  // [NONE, X, Y, Z]
static long maxPosition[4] = {0, MAX_TRAVEL, MAX_TRAVEL, MAX_TRAVEL};
static bool systemHomed[4] = {false, false, false, false};

// ALM states for 5 motors
static MotorALM almStates[MOTOR_COUNT];

// ALM pin mapping
static const uint8_t almPins[MOTOR_COUNT] = {
  ALM_XL_PIN, ALM_XR_PIN, ALM_Y_PIN, ALM_ZL_PIN, ALM_ZR_PIN
};

static const char* motorNames[MOTOR_COUNT] = {
  "X-Left", "X-Right", "Y", "Z-Left", "Z-Right"
};

// -------------------- POSITION FUNCTIONS --------------------

void updatePosition(Axis axis, long steps) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    currentPosition[axis] += steps;
  }
}

long getCurrentPosition(Axis axis) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    return currentPosition[axis];
  }
  return 0;
}

void setCurrentPosition(Axis axis, long position) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    currentPosition[axis] = position;
  }
}

long getMaxPosition(Axis axis) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    return maxPosition[axis];
  }
  return 0;
}

void setMaxPosition(Axis axis, long position) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    maxPosition[axis] = position;
  }
}

int getPositionPercentage(Axis axis) {
  if (axis < AXIS_X || axis > AXIS_Z) return 0;
  if (maxPosition[axis] <= 0) return 0;
  
  int percent = (currentPosition[axis] * 100) / maxPosition[axis];
  if (percent < 0) percent = 0;
  if (percent > 100) percent = 100;
  return percent;
}

// -------------------- SYSTEM STATE --------------------

bool isSystemHomed(Axis axis) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    return systemHomed[axis];
  }
  return false;
}

void setSystemHomed(Axis axis, bool homed) {
  if (axis >= AXIS_X && axis <= AXIS_Z) {
    systemHomed[axis] = homed;
  }
}

bool areAllAxesHomed() {
  return systemHomed[AXIS_X] && systemHomed[AXIS_Y] && systemHomed[AXIS_Z];
}

// -------------------- ALM MONITORING --------------------

void initializeALM() {
  Serial.println("Initializing ALM monitoring for 5 motors:");
  
  for (int i = 0; i < MOTOR_COUNT; i++) {
    pinMode(almPins[i], INPUT_PULLUP);
    
    almStates[i].signal = digitalRead(almPins[i]);
    almStates[i].lastSignal = almStates[i].signal;
    almStates[i].lastCheck = millis();
    almStates[i].pulseStart = 0;
    almStates[i].windowStart = millis();
    almStates[i].pulseCount = 0;
    almStates[i].critical = false;
    almStates[i].timing = false;
    
    Serial.print("  ");
    Serial.print(motorNames[i]);
    Serial.print(" (pin ");
    Serial.print(almPins[i]);
    Serial.print("): ");
    Serial.println(almStates[i].signal == LOW ? "OK" : "ALARM!");
  }
}

MotorALM& getMotorALM(Motor motor) {
  if (motor < MOTOR_COUNT) {
    return almStates[motor];
  }
  return almStates[0];  // fallback
}

void resetALMWindow(Motor motor) {
  if (motor < MOTOR_COUNT) {
    almStates[motor].windowStart = millis();
    almStates[motor].pulseCount = 0;
    almStates[motor].critical = false;
  }
}

void clearAllALM() {
  for (int i = 0; i < MOTOR_COUNT; i++) {
    almStates[i].critical = false;
    almStates[i].pulseCount = 0;
    almStates[i].windowStart = millis();
  }
  Serial.println("All ALM alarms cleared");
}