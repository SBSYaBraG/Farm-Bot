/**
 * CommandProcessor.cpp - Multi-Axis Command Processing Implementation
 * 
 * Parses and executes commands for X, Y, Z axes
 */

#include "CommandProcessor.h"
#include "Config.h"
#include "MotorControl.h"
#include "PositionManager.h"
#include "SystemOperations.h"
#include "ALM_Monitor.h"

extern volatile bool emergencyStopTriggered;

void processCommand(String command) {
  Serial.print("Command received: ");
  Serial.println(command);
  
  command.toUpperCase();
  command.trim();
  
  // Axis movement commands (X1000, Y-500, Z800)
  if (command.startsWith("X")) {
    long steps = command.substring(1).toInt();
    processRelativeMove(AXIS_X, steps);
  }
  else if (command.startsWith("Y")) {
    long steps = command.substring(1).toInt();
    processRelativeMove(AXIS_Y, steps);
  }
  else if (command.startsWith("Z")) {
    long steps = command.substring(1).toInt();
    processRelativeMove(AXIS_Z, steps);
  }
  
  // Absolute positioning (PX25, PY50, PZ75)
  else if (command.startsWith("PX")) {
    int percent = command.substring(2).toInt();
    processAbsoluteMove(AXIS_X, percent);
  }
  else if (command.startsWith("PY")) {
    int percent = command.substring(2).toInt();
    processAbsoluteMove(AXIS_Y, percent);
  }
  else if (command.startsWith("PZ")) {
    int percent = command.substring(2).toInt();
    processAbsoluteMove(AXIS_Z, percent);
  }
  
  // Homing commands
  else if (command == "HX") {
    runHoming(AXIS_X);
  }
  else if (command == "HY") {
    runHoming(AXIS_Y);
  }
  else if (command == "HZ") {
    runHoming(AXIS_Z);
  }
  else if (command == "H" || command == "HALL") {
    runHomingAll();
  }
  
  // System commands
  else if (command == "R" || command == "STATUS") {
    reportStatus();
  }
  else if (command == "S" || command == "STOP") {
    emergencyStop();
  }
  else if (command == "S0" || command == "CLEAR") {
    resumeOperations();
  }
  else if (command == "ALM") {
    printALMStatus();
  }
  
  // Help
  else if (command == "HELP") {
    Serial.println("\n=== FarmBot Multi-Axis Commands ===");
    Serial.println("Movement:");
    Serial.println("  X#### - Move X-axis (e.g. X1000, X-500)");
    Serial.println("  Y#### - Move Y-axis");
    Serial.println("  Z#### - Move Z-axis");
    Serial.println("\nAbsolute:");
    Serial.println("  PX25/50/75 - X to 25%/50%/75%");
    Serial.println("  PY25/50/75 - Y to 25%/50%/75%");
    Serial.println("  PZ25/50/75 - Z to 25%/50%/75%");
    Serial.println("\nHoming:");
    Serial.println("  HX/HY/HZ - Home individual axis");
    Serial.println("  H or HALL - Home all axes");
    Serial.println("\nSystem:");
    Serial.println("  R or STATUS - Show status");
    Serial.println("  S or STOP - Emergency stop");
    Serial.println("  S0 or CLEAR - Clear emergency");
    Serial.println("  ALM - Show ALM status");
    Serial.println("===================================\n");
  }
  
  else {
    Serial.println("Unknown command. Type HELP for command list.");
  }
}

void reportStatus() {
  Serial.println("\n╔════════════════════════════════════╗");
  Serial.println("║       FARMBOT SYSTEM STATUS        ║");
  Serial.println("╠════════════════════════════════════╣");
  
  // X-axis
  Serial.print("║ X-Axis: ");
  Serial.print(isSystemHomed(AXIS_X) ? "HOMED  " : "NOT HOMED");
  Serial.println("                  ║");
  Serial.print("║   Position: ");
  Serial.print(getCurrentPosition(AXIS_X));
  Serial.print(" (");
  Serial.print(getPositionPercentage(AXIS_X));
  Serial.println("%)");
  Serial.print("║   Max: ");
  Serial.println(getMaxPosition(AXIS_X));
  
  // Y-axis
  Serial.print("║ Y-Axis: ");
  Serial.print(isSystemHomed(AXIS_Y) ? "HOMED  " : "NOT HOMED");
  Serial.println("                  ║");
  Serial.print("║   Position: ");
  Serial.print(getCurrentPosition(AXIS_Y));
  Serial.print(" (");
  Serial.print(getPositionPercentage(AXIS_Y));
  Serial.println("%)");
  Serial.print("║   Max: ");
  Serial.println(getMaxPosition(AXIS_Y));
  
  // Z-axis
  Serial.print("║ Z-Axis: ");
  Serial.print(isSystemHomed(AXIS_Z) ? "HOMED  " : "NOT HOMED");
  Serial.println("                  ║");
  Serial.print("║   Position: ");
  Serial.print(getCurrentPosition(AXIS_Z));
  Serial.print(" (");
  Serial.print(getPositionPercentage(AXIS_Z));
  Serial.println("%)");
  Serial.print("║   Max: ");
  Serial.println(getMaxPosition(AXIS_Z));
  
  // System state
  Serial.println("╠════════════════════════════════════╣");
  Serial.print("║ Emergency Stop: ");
  Serial.println(emergencyStopTriggered ? "ACTIVE  " : "Inactive");
  Serial.print("║ ALM Critical: ");
  Serial.println(isAnyALMCritical() ? "YES     " : "No      ");
  Serial.println("╚════════════════════════════════════╝\n");
}

bool checkForEmergencyStop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    input.toUpperCase();
    
    if (input == "S" || input == "STOP") {
      Serial.println("EMERGENCY STOP TRIGGERED DURING MOVEMENT!");
      emergencyStop();
      return true;
    }
  }
  
  return emergencyStopTriggered || isAnyALMCritical();
}