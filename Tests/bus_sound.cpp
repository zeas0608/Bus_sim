#include "BusSoundGenerator.h"
#include <array>
#include <cassert>
#include <cmath>
#include <limits>
using namespace BusAudio;
int main()
{
    Generator synth;
    std::array<int16_t, Generator::Rate> samples{};
    Controls c;
    auto energy = [&](){
        synth.Render(c,samples.data(),samples.size()); double e=0;
        for (auto v:samples) e+=double(v)*v;
        return e/samples.size();
    };
    assert(energy()==0);
    auto bandPower = [&](float hz){
        double a=0, b=0;
        for (int n=Generator::Rate/2; n<Generator::Rate; ++n)
        {
            double phase=6.283185307*hz*n/Generator::Rate;
            a+=samples[n]*std::cos(phase); b+=samples[n]*std::sin(phase);
        }
        return a*a+b*b;
    };
    c.Rpm=650; assert(energy()>10000);
    assert(bandPower(650.f/30)>10*bandPower(2000.f/30));
    c.Rpm=2000; energy();
    assert(bandPower(2000.f/30)>10*bandPower(650.f/30));
    c.Rpm=0; c.DoorMoving=true; assert(energy()>10000);
    c.DoorMoving=false; c.SpeedMS=10; c.Brake=1; assert(energy()>10000);
    c.SpeedMS=0; c.Brake=0; c.Rpm=std::numeric_limits<float>::infinity();
    energy(); assert(energy()<1.0);
}
