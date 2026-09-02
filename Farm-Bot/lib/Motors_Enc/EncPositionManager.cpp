/**
 * EncPositionManager.cpp - Quadrature encoder measurement implementation
 */

#include "EncPositionManager.h"
#include "EncConfig.h"

static volatile long encoderCount = 0;
static volatile long indexCount = 0;
static volatile uint8_t previousState = 0;

// Index = previous AB state (bits 3:2) followed by current AB state (bits 1:0).
// Invalid two-bit jumps are ignored instead of counted as a false step.
static const int8_t quadratureDelta[16] = {
  0, -1,  1,  0,
  1,  0,  0, -1,
 -1,  0,  0,  1,
  0,  1, -1,  0
};

static uint8_t readABState() {
  return (digitalRead(ENCODER_A_PIN) << 1) | digitalRead(ENCODER_B_PIN);
}

static void updateQuadratureCount() {
  const uint8_t currentState = readABState();
  encoderCount += quadratureDelta[(previousState << 2) | currentState];
  previousState = currentState;
}

static void handleEncoderAChange() {
  updateQuadratureCount();
}

static void handleEncoderBChange() {
  updateQuadratureCount();
}

static void handleEncoderIndexRise() {
  indexCount++;
}

void initializeEncPositionManager() {
  pinMode(ENCODER_A_PIN, INPUT);
  pinMode(ENCODER_B_PIN, INPUT);
  pinMode(ENCODER_Z_PIN, INPUT);

  previousState = readABState();
  attachInterrupt(digitalPinToInterrupt(ENCODER_A_PIN), handleEncoderAChange, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_B_PIN), handleEncoderBChange, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_Z_PIN), handleEncoderIndexRise, RISING);
}

long getEncoderCount() {
  noInterrupts();
  const long count = encoderCount;
  interrupts();
  return count;
}

long getEncoderIndexCount() {
  noInterrupts();
  const long count = indexCount;
  interrupts();
  return count;
}

void resetEncoderMeasurements() {
  noInterrupts();
  encoderCount = 0;
  indexCount = 0;
  previousState = readABState();
  interrupts();
}

uint8_t getEncoderState() {
  return readABState();
}

bool getEncoderIndexState() {
  return digitalRead(ENCODER_Z_PIN) == HIGH;
}
