/**
 * ALM_Monitor.h - Multi-Motor ALM Monitoring
 * 
 * Monitors 5 individual ALM signals with pattern detection
 */

#ifndef ALM_MONITOR_H
#define ALM_MONITOR_H

#include <Arduino.h>
#include "Config.h"

void monitorAllALM();
void monitorMotorALM(Motor motor);
bool isAnyALMCritical();
bool isMotorALMCritical(Motor motor);
void printALMStatus();
const char* getMotorName(Motor motor);

#endif // ALM_MONITOR_H