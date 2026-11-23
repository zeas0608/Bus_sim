// Compile the production powertrain with a C++17 compiler; see docs/1086-MT.md.
#include "Vehicle/ManualPowertrain.h"
#include <cassert>
#include <cmath>
#include <limits>
using namespace BusMT;

static void run(Powertrain& p, Input& i, int frames = 60, int hz = 60)
{
    for (int n = 0; n < frames; ++n) p.Advance(1.f/hz, i);
}
static void pulse(Powertrain& p, Input& i, bool up)
{
    i.Up = up; i.Down = !up; run(p,i,1);
    i.Up = i.Down = false; run(p,i,1);
}
static Powertrain launch(int hz)
{
    Powertrain p; Input i;
    p.Ignition(); assert(p.State == Engine::Starting);
    run(p,i,hz,hz); assert(p.State == Engine::Running && p.AxleNm == 0);
    i.Pedal = 1; i.Up = true; run(p,i,hz,hz); assert(p.Gear == 1); // held RB
    i.Up = false; i.Throttle = .36f; run(p,i,hz,hz);
    assert(p.AxleNm == 0 && p.Rpm > 1000);
    i.Pedal = .60f; run(p,i,hz,hz);
    assert(p.SlipRPM > 0 && p.AxleNm > 0);
    return p;
}
int main()
{
    auto p = launch(60); const auto p30 = launch(30);
    assert(std::abs(p.Rpm-p30.Rpm)<.01f && std::abs(p.AxleNm-p30.AxleNm)<.1f);
    Input i; i.Pedal = 1; run(p,i,1); assert(p.AxleNm == 0);
    i.Pedal = .60f; i.Interlock = true; run(p,i,1); assert(p.AxleNm == 0);
    i.Interlock = false; i.Pedal = 0; pulse(p,i,true);
    assert(p.Gear == 1 && p.LastShift == Shift::Clutch);
    run(p,i,240); assert(p.State == Engine::Stalled && p.AxleNm == 0);
    p.Ignition(); assert(p.State == Engine::Stalled); // in gear
    pulse(p,i,false); p.Ignition(); run(p,i); assert(p.State == Engine::Running);
    i.Pedal = 1; i.SpeedMS = 4; pulse(p,i,false);
    assert(p.Gear == 0 && p.LastShift == Shift::Direction);
    i.SpeedMS = 0; pulse(p,i,false);
    i.Throttle=.4f; i.Pedal=.55f; run(p,i); assert(p.Gear == -1 && p.AxleNm < 0);
    i.Throttle=0; i.Pedal=1; pulse(p,i,true); pulse(p,i,true);
    i.SpeedMS=6; i.AxleRadS=11; i.Pedal=0; run(p,i);
    assert(p.State==Engine::Running && p.AxleNm<0); // wheels back-drive engine
    for (float bad : {std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity()})
    {
        i.AxleRadS=bad; run(p,i,1); assert(p.Fault && p.AxleNm==0);
    }
    i.AxleRadS=0; p.Advance(1.f,i); assert(p.Fault && p.AxleNm==0);
    p.Reset(); i={}; i.AutomaticClutch=true; p.Ignition(); run(p,i);
    pulse(p,i,true); i.Throttle=.6f; run(p,i,60);
    assert(p.Gear==1 && p.Engagement>0 && p.AxleNm>0 && p.State==Engine::Running);
    i.Throttle=0; run(p,i,120); assert(p.Gear==1 && p.Engagement==0);
    for (int gear=2; gear<=6; ++gear) {pulse(p,i,true); assert(p.Gear==gear);}
    pulse(p,i,true); assert(p.LastShift==Shift::Limit);
    i.AxleRadS=110; pulse(p,i,false); assert(p.LastShift==Shift::OverRev && p.Gear==6);
}
