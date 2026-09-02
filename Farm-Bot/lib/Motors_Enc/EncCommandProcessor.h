/**
 * EncCommandProcessor.h - Serial command interface for the encoder bench test
 */

#ifndef ENC_COMMAND_PROCESSOR_H
#define ENC_COMMAND_PROCESSOR_H

#include <Arduino.h>

void printEncTestWelcome();
void processEncTestCommand(const String& input);

#endif  // ENC_COMMAND_PROCESSOR_H
