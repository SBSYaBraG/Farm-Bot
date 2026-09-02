/**
 * MotorControl.h - Multi-Axis Motor Control
 * 
 * Controls 3 axes (X, Y, Z) with independent PUL/DIR/ENA
 * Integrated ALM monitoring and emergency stop
 */

#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <Arduino.h>
#include "Config.h"

void initializeMotor();
void enableMotor(Axis axis);
void disableMotor(Axis axis);
void disableAllMotors();
void setDirection(Axis axis, bool direction);
bool moveSteps(Axis axis, long stepsToMove, bool direction);
void stepMotor(Axis axis, int delayTime, bool direction);
void emergencyStop();
void resumeOperations();
void processRelativeMove(Axis axis, long steps);
void processAbsoluteMove(Axis axis, int percentage);
bool isEmergencyStopActive();

#endif // MOTOR_CONTROL_H