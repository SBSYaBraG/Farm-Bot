/**
 * EncCommandProcessor.cpp - Serial command interface implementation
 */

#include "EncCommandProcessor.h"
#include "EncConfig.h"
#include "EncMotorControl.h"
#include "EncPositionManager.h"

static unsigned long logSequence = 0;

static long absoluteLong(long value) {
  return value < 0 ? -value : value;
}

static void printHelp() {
  Serial.println("\nENCODER BENCH-TEST COMMANDS");
  Serial.println("  STATUS              Show encoder inputs and measurements");
  Serial.println("  ZERO                Reset encoder and index counts");
  Serial.println("  F <pulses>          Forward constant-speed move (100 PPS)");
  Serial.println("  R <pulses>          Reverse constant-speed move (100 PPS)");
  Serial.println("  RF <pulses> <pps>   Forward move with accel/decel");
  Serial.println("  RR <pulses> <pps>   Reverse move with accel/decel");
  Serial.println("  HELP                Show this command list\n");
}

static void printStatus() {
  const uint8_t abState = getEncoderState();
  Serial.println("\n=== ENCODER BENCH STATUS ===");
  Serial.print("Encoder count: ");
  Serial.println(getEncoderCount());
  Serial.print("Index count: ");
  Serial.println(getEncoderIndexCount());
  Serial.print("A/B state: ");
  Serial.print((abState >> 1) & 1);
  Serial.print('/');
  Serial.println(abState & 1);
  Serial.print("Z state: ");
  Serial.println(getEncoderIndexState() ? 1 : 0);
  Serial.print("Driver pulse/rev: ");
  Serial.println(TB6600_PULSES_PER_REV);
  Serial.print("Expected encoder counts/rev: ");
  Serial.println(ENCODER_COUNTS_PER_REV);
  Serial.println("===========================\n");
}

static long parsePositivePulses(const String& text) {
  const long pulses = text.toInt();
  if (pulses <= 0) {
    Serial.println("ERROR: Pulses must be a positive whole number.");
    return 0;
  }
  return pulses;
}

static bool parseRampArguments(const String& input, long& pulses, unsigned int& targetPps) {
  const int firstSpace = input.indexOf(' ');
  const int secondSpace = input.indexOf(' ', firstSpace + 1);
  if (firstSpace < 0 || secondSpace < 0) {
    Serial.println("ERROR: Use RF <pulses> <pps> or RR <pulses> <pps>.");
    return false;
  }

  pulses = parsePositivePulses(input.substring(firstSpace + 1, secondSpace));
  const long requestedPps = input.substring(secondSpace + 1).toInt();
  if (pulses == 0 || requestedPps <= 0) {
    Serial.println("ERROR: Pulses and PPS must be positive whole numbers.");
    return false;
  }

  targetPps = static_cast<unsigned int>(requestedPps);
  return true;
}

static void printMoveLog(const EncMoveResult& result) {
  const long encoderDelta = result.encoderAfter - result.encoderBefore;
  const long expectedMagnitude = (result.commandedPulses * ENCODER_COUNTS_PER_REV) / TB6600_PULSES_PER_REV;
  const long magnitudeError = absoluteLong(absoluteLong(encoderDelta) - expectedMagnitude);
  const long indexDelta = result.indexAfter - result.indexBefore;

  Serial.print("Move complete. Encoder delta: ");
  Serial.print(encoderDelta);
  Serial.print(" | expected magnitude: ");
  Serial.print(expectedMagnitude);
  Serial.print(" | magnitude error: ");
  Serial.println(magnitudeError);

  Serial.print("ENC_LOG,");
  Serial.print(++logSequence);
  Serial.print(',');
  Serial.print(result.type == EncMoveType::Ramp ? "RAMP" : "CONSTANT");
  Serial.print(',');
  Serial.print(result.forward ? "FORWARD" : "REVERSE");
  Serial.print(',');
  Serial.print(result.commandedPulses);
  Serial.print(',');
  Serial.print(result.targetPps);
  Serial.print(',');
  Serial.print(result.durationMs);
  Serial.print(',');
  Serial.print(result.encoderBefore);
  Serial.print(',');
  Serial.print(result.encoderAfter);
  Serial.print(',');
  Serial.print(encoderDelta);
  Serial.print(',');
  Serial.print(expectedMagnitude);
  Serial.print(',');
  Serial.print(magnitudeError);
  Serial.print(',');
  Serial.print(result.indexBefore);
  Serial.print(',');
  Serial.println(result.indexAfter);
  Serial.print("Index delta: ");
  Serial.println(indexDelta);
}

void printEncTestWelcome() {
  Serial.println("\n============================================");
  Serial.println("  17HS19-2004-ME1K ENCODER BENCH TEST");
  Serial.println("============================================");
  Serial.println("TB6600: PUL D39, DIR D43, ENA D41 unused");
  Serial.println("Encoder: A D2, B D3, Z D20");
  Serial.println("Start with TB6600 at 1.5 A and 400 pulses/rev.");
  Serial.println("Keep the shaft unloaded and clear before motion.");
  printHelp();
  Serial.println("CSV format: ENC_LOG,sequence,type,direction,command_pulses,target_pps,duration_ms,encoder_before,encoder_after,encoder_delta,expected_magnitude,magnitude_error,index_before,index_after");
}

void processEncTestCommand(const String& receivedInput) {
  String input = receivedInput;
  input.trim();
  input.toUpperCase();

  if (input == "HELP") {
    printHelp();
  } else if (input == "STATUS") {
    printStatus();
  } else if (input == "ZERO") {
    resetEncoderMeasurements();
    Serial.println("Encoder and index counts reset to zero.");
  } else if (input.startsWith("F ")) {
    const long pulses = parsePositivePulses(input.substring(2));
    if (pulses > 0) printMoveLog(moveEncMotorConstant(pulses, true));
  } else if (input.startsWith("R ")) {
    const long pulses = parsePositivePulses(input.substring(2));
    if (pulses > 0) printMoveLog(moveEncMotorConstant(pulses, false));
  } else if (input.startsWith("RF ") || input.startsWith("RR ")) {
    long pulses = 0;
    unsigned int targetPps = 0;
    if (parseRampArguments(input, pulses, targetPps)) {
      printMoveLog(moveEncMotorRamp(pulses, input.startsWith("RF "), targetPps));
    }
  } else {
    Serial.println("ERROR: Unknown command. Send HELP for commands.");
  }
}
