#pragma once

namespace BusDrive
{
// Shared safety controls. Preserve the original AT pressure ramp supplied by the base pawn.
struct Controls
{
    bool DriveAllowed;
    float ServiceBrake;
};
inline Controls Interlock(bool Park, bool DoorMovingOrOpen, bool Fault, float Brake)
{
    return {!Park && !DoorMovingOrOpen && !Fault, (DoorMovingOrOpen || Fault) ? 1.f : Brake};
}
}
