/**
 * Config.h - Multi-Axis FarmBot Configuration
 * 
 * 5-motor system: X(2 motors), Y(1 motor), Z(2 motors)
 * Each axis has independent control and limit switches
 * All 5 motors have individual ALM monitoring
 */

#ifndef CONFIG_H
#define CONFIG_H

// -------------------- X-AXIS PINS (6) --------------------
#define X_PUL_PIN 51
#define X_DIR_PIN 53
#define X_ENA_PIN 49
#define X_LIMIT_PIN 26
#define ALM_XL_PIN 37     // X Left motor
#define ALM_XR_PIN 39     // X Right motor

// -------------------- Y-AXIS PINS (5) --------------------
#define Y_PUL_PIN 50
#define Y_DIR_PIN 52
#define Y_ENA_PIN 48
#define Y_LIMIT_PIN 24
#define ALM_Y_PIN 31      // Y motor

// -------------------- Z-AXIS PINS (6) --------------------
#define Z_PUL_PIN 42
#define Z_DIR_PIN 44
#define Z_ENA_PIN 40
#define Z_LIMIT_PIN 22
#define ALM_ZL_PIN 33     // Z Left motor
#define ALM_ZR_PIN 35     // Z Right motor

// -------------------- MOTOR CONSTANTS --------------------
#define CW false
#define CCW true

// Homing directions per axis
#define X_HOME_DIRECTION CW
#define Y_HOME_DIRECTION CW
#define Z_HOME_DIRECTION CW

// Speed control (microseconds)
#define MIN_STEP_DELAY 80
#define MAX_STEP_DELAY 175
#define HOMING_STEP_DELAY 200
#define ACCEL_RATE 10
#define DECEL_RATE 10

// -------------------- SAFETY --------------------
#define BACKOFF_STEPS 1600
#define MAX_TRAVEL 100000000
#define HOMING_TIMEOUT 100000000
#define AUTO_HOME_ON_STARTUP true
#define EMERGENCY_CHECK_INTERVAL 10
#define ENA_STABILIZATION_TIME 200  // ms before first pulse

// -------------------- ALM MONITORING --------------------
#define EXPECTED_BLINK_DURATION 200
#define BLINK_TOLERANCE 50
#define PATTERN_WINDOW 5000
#define ALM_CHECK_INTERVAL 1
#define CONTINUOUS_ALARM_TIME 10000

#define ALM_OVERCURRENT_PATTERN 1
#define ALM_OVERVOLTAGE_PATTERN 2
#define ALM_POSITION_ERROR_PATTERN 7

// -------------------- SYSTEM --------------------
#define SERIAL_BAUD_RATE 115200

// Axis enumeration
enum Axis {
  AXIS_NONE = 0,
  AXIS_X = 1,
  AXIS_Y = 2,
  AXIS_Z = 3
};

// Motor enumeration
enum Motor {
  MOTOR_XL = 0,  // X Left
  MOTOR_XR = 1,  // X Right
  MOTOR_Y = 2,   // Y
  MOTOR_ZL = 3,  // Z Left
  MOTOR_ZR = 4,  // Z Right
  MOTOR_COUNT = 5
};

#endif // CONFIG_H