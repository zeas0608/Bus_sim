#pragma once

#include <array>

// SI units; fictional 1086 training gearbox. Independent of UE and the Chaos AT.
namespace BusMT
{
enum class Engine { Off, Starting, Running, Stalled };
enum class Shift { Accepted, BothButtons, Clutch, Direction, OverRev, Limit };

struct Tuning
{
    std::array<float, 6> Forward{5.20f, 3.15f, 2.05f, 1.45f, 1.0f, 0.76f};
    float Reverse = 5.1f;
    float FinalDrive = 5.0f;
    float Inertia = 2.4f;           // kg m^2
    float PeakNm = 650.f;
    float CapacityNm = 980.f;
    float Coupling = 18.f;          // Nm per rad/s of slip
    float IdleRPM = 650.f;
    float LimitRPM = 2800.f;
    bool Valid() const;
};

struct Input
{
    float Throttle = 0;
    float Pedal = 0;                // LT = 1 fully released torque path
    float AxleRadS = 0;             // signed mean rear wheel speed
    float SpeedMS = 0;
    bool Interlock = false;         // doors or park
    bool AutomaticClutch = false;
    bool Up = false;
    bool Down = false;
};

struct Powertrain
{
    Tuning Setup;
    Engine State = Engine::Off;
    Shift LastShift = Shift::Accepted;
    int Gear = 0;
    float Rpm = 0;
    float Engagement = 0;
    float SlipRPM = 0;
    float AxleNm = 0;
    bool Fault = false;

    void Ignition();
    void Advance(float Seconds, const Input& In);
    void Reset();
    void SynchronizeButtons(bool Up, bool Down);

private:
    float Ratio(int Selected) const;
    void ShiftOnce(const Input& In);
    void Step(float Dt, const Input& In);
    double Remainder = 0;
    float StarterTime = 0;
    float ShiftDelay = 0;
    float LowRpmTime = 0;
    bool WasUp = false;
    bool WasDown = false;
};
}
