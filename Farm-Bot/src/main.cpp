/**
 * main.cpp - FarmBot Multi-Axis Controller
 * 
 * 4-motor system with X, Y, Z axis control:
 * - X-axis: 2 motors synchronized (XL, XR)
 * - Y-axis: 1 motor
 * - Z-axis: 1 motor (ZL driver connection)
 * - Individual ALM monitoring for all active motors
 * - Auto-homing at startup
 * - Full position tracking and safety features
 */

#include "Config.h"
#include "MotorControl.h"
#include "PositionManager.h"
#include "LimitSwitch.h"
#include "CommandProcessor.h"
#include "SystemOperations.h"
#include "ALM_Monitor.h"

extern volatile bool emergencyStopTriggered;

bool autoHomingComplete = false;
bool autoHomingInProgress = false;
unsigned long startupTime = 0;

void printWelcomeMessage() {
  Serial.println("\n╔═══════════════════════════════════════════════╗");
  Serial.println("║    FarmBot Multi-Axis Controller v2.0        ║");
  Serial.println("╠═══════════════════════════════════════════════╣");
  Serial.println("║ Configuration:                                ║");
  Serial.println("║  • X-Axis: 2 motors (XL, XR) synchronized    ║");
  Serial.println("║  • Y-Axis: 1 motor                            ║");
  Serial.println("║  • Z-Axis: 1 motor                            ║");
  Serial.println("║  • Total: 4 motors, 4 ALM monitors           ║");
  Serial.println("║  • 3 limit switches (X, Y, Z)                ║");
  Serial.println("╠═══════════════════════════════════════════════╣");
  Serial.println("║ Quick Commands:                               ║");
  Serial.println("║  X1000  - Move X 1000 steps forward          ║");
  Serial.println("║  Y-500  - Move Y 500 steps backward          ║");
  Serial.println("║  Z800   - Move Z 800 steps forward           ║");
  Serial.println("║  H      - Home all axes                       ║");
  Serial.println("║  STATUS - Show system status                  ║");
  Serial.println("║  HELP   - Full command list                   ║");
  Serial.println("╠═══════════════════════════════════════════════╣");
  Serial.println("║ ALM monitoring active 24/7 for all motors    ║");
  Serial.println("╚═══════════════════════════════════════════════╝\n");
}

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  delay(100);
  
  Serial.println("\n========================================");
  Serial.println("   FarmBot Multi-Axis Controller");
  Serial.println("========================================");
  Serial.println("Initializing systems...\n");
  
  // Initialize all subsystems
  initializeMotor();
  initializeLimitSwitch();
  
  Serial.println("\nAll systems initialized successfully!");
  Serial.println("ALM monitoring active for all 4 active motors");
  
  if (AUTO_HOME_ON_STARTUP) {
    Serial.println("\nAuto-homing enabled - starting in 3 seconds");
    Serial.println("Send 'STOP' to cancel auto-homing");
    Serial.println("Waiting...");
  } else {
    Serial.println("\nAuto-homing disabled");
    Serial.println("Send 'H' or 'HALL' to home all axes");
    autoHomingComplete = true;
    printWelcomeMessage();
  }
  
  startupTime = millis();
}

void loop() {
  // CRITICAL: Continuous ALM monitoring
  monitorAllALM();
  
  // Handle auto-homing startup
  if (AUTO_HOME_ON_STARTUP && !autoHomingComplete && !autoHomingInProgress) {
    if (millis() - startupTime > 3000) {
      Serial.println("\n>>> Starting auto-homing sequence <<<");
      autoHomingInProgress = true;
      runHomingAll();
      autoHomingInProgress = false;
      autoHomingComplete = true;
      
      if (areAllAxesHomed()) {
        printWelcomeMessage();
        Serial.println(">>> System ready for commands <<<\n");
      } else {
        Serial.println("\nWARNING: Auto-homing incomplete");
        Serial.println("Use HX, HY, HZ to home individual axes");
        Serial.println("Or send H/HALL to retry all axes");
      }
    }
  }
  
  // Process serial commands
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    // Handle emergency stop during auto-homing
    if ((input.equalsIgnoreCase("S") || input.equalsIgnoreCase("STOP")) && autoHomingInProgress) {
      Serial.println("\n>>> Auto-homing cancelled by user <<<");
      emergencyStop();
      autoHomingInProgress = false;
      autoHomingComplete = true;
      Serial.println("Send CLEAR to resume operations");
      Serial.println("Send H to retry homing");
    }
    // Process normal commands
    else if (input.length() > 0) {
      processCommand(input);
    }
  }
  
  delay(5);  // Small delay for ALM responsiveness
}