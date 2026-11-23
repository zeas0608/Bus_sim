#pragma once
#include <cstdint>

namespace BusAudio
{
struct Controls
{
    float Rpm = 0, Load = 0, Throttle = 0, SpeedMS = 0, Brake = 0;
    bool DoorMoving = false, InCab = true;
    int Gear = 0;
};

class Generator
{
public:
    static constexpr int Rate = 24000;
    void Render(const Controls& Controls, int16_t* Out, int Count);
private:
    double Phase = 0;
    float Rpm = 0, Load = 0, Throttle = 0, Road = 0, Brake = 0, Door = 0, GearClick = 0;
    float NoiseLow = 0, NoiseMid = 0;
    uint32_t Seed = 1086;
    int LastGear = 0;
};
}
