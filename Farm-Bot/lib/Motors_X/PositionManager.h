/**
 * PositionManager.h - Multi-Axis Position and State Management
 * 
 * Tracks position, limits, homing status for X, Y, Z axes
 * and ALM state for all 5 motors
 */

#ifndef POSITION_MANAGER_H
#define POSITION_MANAGER_H

#include <Arduino.h>
#include "Config.h"

// -------------------- POSITION MANAGEMENT --------------------

void updatePosition(Axis axis, long steps);
long getCurrentPosition(Axis axis);
void setCurrentPosition(Axis axis, long position);
long getMaxPosition(Axis axis);
void setMaxPosition(Axis axis, long position);
int getPositionPercentage(Axis axis);

// -------------------- SYSTEM STATE --------------------

bool isSystemHomed(Axis axis);
void setSystemHomed(Axis axis, bool homed);
bool areAllAxesHomed();

// -------------------- ALM MONITORING --------------------

struct MotorALM {
  bool signal;
  bool lastSignal;
  unsigned long lastCheck;
  unsigned long pulseStart;
  unsigned long windowStart;
  byte pulseCount;
  bool critical;
  bool timing;
};

MotorALM& getMotorALM(Motor motor);
void initializeALM();
void resetALMWindow(Motor motor);
void clearAllALM();

#endif // POSITION_MANAGER_H