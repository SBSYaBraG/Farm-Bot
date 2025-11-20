/**
 * ALM_Monitor.cpp - Multi-Motor ALM Implementation
 * 
 * Monitors 5 ALM signals independently
 */

#include "ALM_Monitor.h"
#include "PositionManager.h"
#include "MotorControl.h"

static const char* motorNames[MOTOR_COUNT] = {
  "X-Left", "X-Right", "Y", "Z-Left", "Z-Right"
};

static const uint8_t almPins[MOTOR_COUNT] = {
  ALM_XL_PIN, ALM_XR_PIN, ALM_Y_PIN, ALM_ZL_PIN, ALM_ZR_PIN
};

static void handleCritical(Motor motor, const char* type) {
  getMotorALM(motor).critical = true;
  Serial.print("\n!!! CRITICAL: ");
  Serial.print(motorNames[motor]);
  Serial.print(" - ");
  Serial.print(type);
  Serial.println(" !!!\n");
}

static void processPattern(Motor motor, byte count) {
  Serial.print("\n=== ALM ");
  Serial.print(motorNames[motor]);
  Serial.print(": ");
  Serial.print(count);
  Serial.println(" pulses ===");
  
  switch (count) {
    case ALM_OVERCURRENT_PATTERN:
      Serial.println("OVER-CURRENT!");
      handleCritical(motor, "OVERCURRENT");
      break;
    case ALM_OVERVOLTAGE_PATTERN:
      Serial.println("OVER-VOLTAGE!");
      handleCritical(motor, "OVERVOLTAGE");
      break;
    case ALM_POSITION_ERROR_PATTERN:
      Serial.println("POSITION ERROR (warning)");
      break;
    default:
      Serial.print("UNKNOWN (");
      Serial.print(count);
      Serial.println(")");
      break;
  }
  Serial.println("==================\n");
}

void monitorAllALM() {
  for (int i = 0; i < MOTOR_COUNT; i++) {
    monitorMotorALM((Motor)i);
  }
}

void monitorMotorALM(Motor motor) {
  if (motor >= MOTOR_COUNT) return;
  
  MotorALM& alm = getMotorALM(motor);
  unsigned long now = millis();
  
  // Rate limit
  if (now - alm.lastCheck < ALM_CHECK_INTERVAL) return;
  alm.lastCheck = now;
  
  // Read signal
  alm.signal = digitalRead(almPins[motor]);
  
  // Edge detection
  if (alm.lastSignal != alm.signal) {
    
    // LOW → HIGH (pulse start)
    if (!alm.lastSignal && alm.signal) {
      alm.pulseStart = now;
      alm.timing = true;
    }
    
    // HIGH → LOW (pulse end)
    else if (alm.lastSignal && !alm.signal && alm.timing) {
      unsigned long duration = now - alm.pulseStart;
      
      // Validate pulse (~200ms ± 50ms)
      if (abs((int)duration - EXPECTED_BLINK_DURATION) <= BLINK_TOLERANCE) {
        alm.pulseCount++;
        Serial.print("ALM ");
        Serial.print(motorNames[motor]);
        Serial.print(": ");
        Serial.print(duration);
        Serial.print("ms, count=");
        Serial.println(alm.pulseCount);
      }
      alm.timing = false;
    }
    
    alm.lastSignal = alm.signal;
  }
  
  // Check 5-second window
  if (now - alm.windowStart >= PATTERN_WINDOW) {
    if (alm.pulseCount > 0) {
      processPattern(motor, alm.pulseCount);
    }
    resetALMWindow(motor);
  }
  
  // Check continuous alarm
  if (alm.pulseCount > 0 && 
      now - alm.windowStart >= CONTINUOUS_ALARM_TIME) {
    handleCritical(motor, "CONTINUOUS");
  }
}

bool isAnyALMCritical() {
  for (int i = 0; i < MOTOR_COUNT; i++) {
    if (getMotorALM((Motor)i).critical) return true;
  }
  return false;
}

bool isMotorALMCritical(Motor motor) {
  return getMotorALM(motor).critical;
}

void printALMStatus() {
  Serial.println("\n=== ALM STATUS ===");
  for (int i = 0; i < MOTOR_COUNT; i++) {
    MotorALM& alm = getMotorALM((Motor)i);
    Serial.print(motorNames[i]);
    Serial.print(": ");
    Serial.print(alm.signal == LOW ? "OK" : "ALARM");
    Serial.print(" | Pulses: ");
    Serial.print(alm.pulseCount);
    Serial.print(" | Critical: ");
    Serial.println(alm.critical ? "YES" : "No");
  }
  Serial.println("==================\n");
}

const char* getMotorName(Motor motor) {
  if (motor < MOTOR_COUNT) return motorNames[motor];
  return "Unknown";
}