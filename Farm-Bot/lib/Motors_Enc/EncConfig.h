/**
 * EncConfig.h - Encoder-motor bench-test configuration
 *
 * This configuration is only for the 17HS19-2004-ME1K and TB6600 bench test.
 */

#ifndef ENC_CONFIG_H
#define ENC_CONFIG_H

#include <Arduino.h>

// TB6600 common-cathode command wiring
constexpr uint8_t TB6600_PUL_PIN = 39;
constexpr uint8_t TB6600_DIR_PIN = 43;
constexpr uint8_t TB6600_ENA_PIN = 41;

// 17HS19-2004-ME1K encoder positive signal wiring
constexpr uint8_t ENCODER_A_PIN = 2;   // EA+ (brown), external interrupt
constexpr uint8_t ENCODER_B_PIN = 3;   // EB+ (blue), external interrupt
constexpr uint8_t ENCODER_Z_PIN = 20;  // EZ+ (yellow), external interrupt

// Motor and driver settings
constexpr long ENCODER_COUNTS_PER_REV = 4000L;
constexpr long TB6600_PULSES_PER_REV = 400L;  // Current TB6600 setting: 1/2 step.
constexpr bool FORWARD_DIR_LEVEL = HIGH;

// TB6600 timing requirements are exceeded deliberately for a reliable bench test.
constexpr unsigned int PULSE_HIGH_US = 5;
constexpr unsigned int DIRECTION_SETUP_US = 10;
constexpr unsigned int CONSTANT_TEST_PPS = 100;
constexpr unsigned int RAMP_START_PPS = 100;
constexpr unsigned int RAMP_MAX_PPS = 600;

#endif  // ENC_CONFIG_H
