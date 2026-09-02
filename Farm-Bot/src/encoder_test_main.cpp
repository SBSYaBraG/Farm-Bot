/**
 * encoder_test_main.cpp - Isolated 17HS19-2004-ME1K motor and encoder test
 *
 * The PlatformIO encoder-test environment excludes main.cpp and builds this
 * file instead. No FarmBot homing, limit-switch, or gantry code runs here.
 */

#include <Arduino.h>

#include "EncCommandProcessor.h"
#include "EncMotorControl.h"
#include "EncPositionManager.h"

static String serialInput;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);

  initializeEncPositionManager();
  initializeEncMotorControl();
  printEncTestWelcome();
}

void loop() {
  while (Serial.available() > 0) {
    const char received = static_cast<char>(Serial.read());

    if (received == '\n' || received == '\r') {
      if (serialInput.length() > 0) {
        processEncTestCommand(serialInput);
        serialInput = "";
      }
    } else if (serialInput.length() < 48) {
      serialInput += received;
    } else {
      serialInput = "";
      Serial.println("ERROR: Command too long.");
    }
  }
}
