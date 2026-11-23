#include "Vehicle/ManualPowertrain.h"
#include <algorithm>
#include <cmath>

namespace BusMT
{
namespace
{
constexpr float RpmPerRadS = 9.5492966f;
constexpr double StepSeconds = 1.0 / 120.0;
bool Within(float V, float Lo, float Hi) { return std::isfinite(V) && V >= Lo && V <= Hi; }
}

bool Tuning::Valid() const
{
    return std::all_of(Forward.begin(), Forward.end(), [](float V){ return Within(V, .1f, 20.f); })
        && Within(Reverse,.1f,20.f) && Within(FinalDrive,.1f,20.f) && Within(Inertia,.1f,50.f)
        && Within(PeakNm,1,5000) && Within(CapacityNm,1,10000) && Within(Coupling,1,100)
        && Within(IdleRPM,400,1200) && Within(LimitRPM,IdleRPM + 500,6000);
}

float Powertrain::Ratio(int Selected) const
{
    if (Selected == 0) return 0;
    return Setup.FinalDrive * (Selected < 0 ? -Setup.Reverse : Setup.Forward[Selected-1]);
}

void Powertrain::Reset()
{
    const Tuning Saved = Setup;
    *this = Powertrain{};
    Setup = Saved;
}

void Powertrain::Ignition()
{
    if (State == Engine::Running || State == Engine::Starting) { Reset(); return; }
    if (Gear != 0 || Fault) return;
    State = Engine::Starting;
    StarterTime = LowRpmTime = 0;
}

void Powertrain::SynchronizeButtons(bool Up, bool Down)
{
    WasUp = Up;
    WasDown = Down;
}

void Powertrain::ShiftOnce(const Input& In)
{
    const bool UpEdge = In.Up && !WasUp;
    const bool DownEdge = In.Down && !WasDown;
    SynchronizeButtons(In.Up, In.Down);
    if (!UpEdge && !DownEdge) return;
    const int Target = Gear + (UpEdge ? 1 : -1);
    if (In.Up && In.Down) LastShift = Shift::BothButtons;
    else if (Target < -1 || Target > 6) LastShift = Shift::Limit;
    else if ((Target < 0 && std::abs(In.SpeedMS) > .22f) || (Target > 0 && In.SpeedMS < -.6f))
        LastShift = Shift::Direction;
    else if (Target != 0 && !In.AutomaticClutch && In.Pedal < .85f) LastShift = Shift::Clutch;
    else if (Target != 0 && In.AxleRadS * Ratio(Target) * RpmPerRadS > Setup.LimitRPM)
        LastShift = Shift::OverRev;
    else
    {
        Gear = Target;
        AxleNm = 0;
        ShiftDelay = .22f;
        if (In.AutomaticClutch) Engagement = 0;
        LastShift = Shift::Accepted;
    }
}

void Powertrain::Advance(float Seconds, const Input& In)
{
    Fault = !Setup.Valid() || !Within(Seconds,0,.25f) || !Within(In.Throttle,0,1)
        || !Within(In.Pedal,0,1) || !Within(In.AxleRadS,-2000,2000) || !Within(In.SpeedMS,-200,200);
    if (Fault)
    {
        AxleNm = SlipRPM = Engagement = 0;
        Remainder = 0;
        SynchronizeButtons(In.Up, In.Down);
        return;
    }
    ShiftOnce(In);
    Remainder += Seconds;
    while (Remainder + 1e-10 >= StepSeconds)
    {
        Step(static_cast<float>(StepSeconds), In);
        Remainder -= StepSeconds;
    }
    if (In.Interlock || Gear == 0 || (!In.AutomaticClutch && In.Pedal == 1.f)) AxleNm = 0;
}

void Powertrain::Step(float Dt, const Input& In)
{
    ShiftDelay = std::max(0.f, ShiftDelay - Dt);
    const float RatioNow = Ratio(Gear);
    const float ShaftRPM = In.AxleRadS * RatioNow * RpmPerRadS;
    if (State != Engine::Running)
    {
        AxleNm = Engagement = SlipRPM = 0;
        if (State == Engine::Starting)
        {
            StarterTime += Dt;
            Rpm = Setup.IdleRPM * std::min(1.f, StarterTime / .65f);
            if (StarterTime >= .65f) State = Engine::Running;
        }
        else Rpm = 0;
        return;
    }
    const float Demand = In.Interlock ? 0.f : In.Throttle;
    if (In.AutomaticClutch)
    {
        // Ease into bite at standstill, then lock as the road catches up.
        const float Target = ShiftDelay > 0 || In.Interlock || Gear == 0 ? 0.f :
            std::clamp(Demand * .63f + std::max(0.f,ShaftRPM) / Setup.IdleRPM, 0.f, 1.f)
            * std::clamp((Rpm - .55f*Setup.IdleRPM) / (.45f*Setup.IdleRPM), 0.f, 1.f);
        Engagement += std::clamp(Target - Engagement, -5.f*Dt, 1.4f*Dt);
    }
    else Engagement = 1.f - In.Pedal;

    SlipRPM = RatioNow == 0 ? 0.f : Rpm - ShaftRPM;
    const float Capacity = Setup.CapacityNm * Engagement * Engagement;
    const float ClutchNm = RatioNow == 0 || In.Interlock || ShiftDelay > 0 ? 0.f :
        std::clamp(Setup.Coupling * SlipRPM / RpmPerRadS, -Capacity, Capacity);
    const float Drag = 28.f + .032f*Rpm;
    const float IdleNm = std::clamp(Drag + (Setup.IdleRPM-Rpm)*1.25f, 0.f, .38f*Setup.PeakNm);
    const float Curve = std::clamp(1.f - .00000018f*(Rpm-1450.f)*(Rpm-1450.f), .40f, 1.f);
    const float Governor = std::clamp((Setup.LimitRPM - Rpm)/160.f, 0.f, 1.f);
    const float Combustion = std::max(IdleNm, Demand * Setup.PeakNm * Curve * Governor);
    Rpm = std::clamp(Rpm + (Combustion - Drag - ClutchNm)*Dt*RpmPerRadS/Setup.Inertia,
                     0.f, Setup.LimitRPM * 1.2f);
    AxleNm = ClutchNm * RatioNow * .92f;
    LowRpmTime = Rpm < .53f*Setup.IdleRPM ? LowRpmTime + Dt : 0.f;
    if (LowRpmTime >= .12f)
    {
        State = Engine::Stalled;
        AxleNm = Rpm = 0;
    }
}
}
