#include "BusSoundGenerator.h"
#include <algorithm>
#include <cmath>

void BusAudio::Generator::Render(const Controls& In, int16_t* Out, int Count)
{
    // Original four-cylinder/four-stroke approximation, two firing pulses per revolution.
    constexpr double Tau = 6.283185307179586;
    auto sane = [](float V, float Hi){ return std::isfinite(V) ? std::clamp(V,0.f,Hi) : 0.f; };
    const float TargetRpm = sane(In.Rpm,4800);
    const float TargetLoad = sane(In.Load,1);
    const float TargetThrottle = sane(In.Throttle,1);
    const float TargetRoad = sane(std::abs(In.SpeedMS)/24.f,1);
    const float TargetBrake = sane(In.Brake,1)*std::min(1.f,TargetRoad*12.f);
    if (LastGear != In.Gear) { LastGear = In.Gear; GearClick = .13f; }
    for (int N = 0; N < Count; ++N)
    {
        Rpm += .0015f*(TargetRpm-Rpm);
        Load += .001f*(TargetLoad-Load);
        Throttle += .001f*(TargetThrottle-Throttle);
        Road += .001f*(TargetRoad-Road);
        Brake += .003f*(TargetBrake-Brake);
        Door += .002f*(static_cast<float>(In.DoorMoving)-Door);
        Phase += Tau * Rpm / (30. * Rate);
        if (Phase >= Tau) Phase -= Tau;
        Seed = 1664525u*Seed + 1013904223u;
        const float Noise = static_cast<float>(Seed >> 8)/8388608.f-1.f;
        NoiseLow += .06f*(Noise-NoiseLow);
        NoiseMid += .32f*(Noise-NoiseMid);
        const float Pulse = static_cast<float>(std::sin(Phase) + (.3f+.3f*Load)*std::sin(2*Phase)
            + (.12f+.20f*Throttle)*std::sin(4*Phase));
        const float Running = std::min(1.f,Rpm/400.f);
        const float Engine = Running*((.13f+.10f*Load)*Pulse+.03f*NoiseLow);
        const float Air = (.18f*Brake+.26f*Door)*(Noise-NoiseMid);
        const float Mix = (In.InCab ? .75f : 1.f)*Engine + Road*.24f*NoiseLow
            + Air*(In.InCab ? .66f : 1.f) + GearClick*NoiseMid;
        GearClick *= .997f;
        Out[N] = static_cast<int16_t>(std::clamp(Mix,-.95f,.95f)*32767.f);
    }
}
