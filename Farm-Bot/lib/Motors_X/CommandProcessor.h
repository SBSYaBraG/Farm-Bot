/**
 * CommandProcessor.h - Multi-Axis Command Processing
 * 
 * Handles serial commands for X, Y, Z axes with ALM integration
 */

#ifndef COMMAND_PROCESSOR_H
#define COMMAND_PROCESSOR_H

#include <Arduino.h>

void processCommand(String command);
void reportStatus();
bool checkForEmergencyStop();

#endif // COMMAND_PROCESSOR_H