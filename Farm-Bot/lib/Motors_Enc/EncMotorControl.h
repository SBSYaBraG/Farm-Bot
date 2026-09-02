/**
 * EncMotorControl.h - TB6600 pulse generation for the bench test
 */

#ifndef ENC_MOTOR_CONTROL_H
#define ENC_MOTOR_CONTROL_H

#include <Arduino.h>

enum class EncMoveType : uint8_t {
  ConstantSpeed,
  Ramp
};

struct EncMoveResult {
  long commandedPulses;
  long encoderBefore;
  long encoderAfter;
  long indexBefore;
  long indexAfter;
  unsigned long durationMs;
  unsigned int targetPps;
  bool forward;
  EncMoveType type;
};

void initializeEncMotorControl();
EncMoveResult moveEncMotorConstant(long pulses, bool forward);
EncMoveResult moveEncMotorRamp(long pulses, bool forward, unsigned int targetPps);

#endif  // ENC_MOTOR_CONTROL_H
