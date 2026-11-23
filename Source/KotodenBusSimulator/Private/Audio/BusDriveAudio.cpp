#include "BusDriveAudio.h"
#include "Sound/SoundWaveProcedural.h"

void UBusDriveAudio::Update(const BusAudio::Controls& Controls)
{
    if (!Wave)
    {
        Wave = NewObject<USoundWaveProcedural>(this);
        Wave->SetSampleRate(BusAudio::Generator::Rate);
        Wave->NumChannels = 1;
        Wave->Duration = INDEFINITELY_LOOPING_DURATION;
        SetSound(Wave);
    }
    // Maintain 100ms of PCM. Frame stalls may cause a short underrun, never an unbounded queue.
    int16 Samples[512];
    int32 Needed = BusAudio::Generator::Rate/10 - Wave->GetAvailableAudioByteCount()/static_cast<int32>(sizeof(int16));
    while (Needed > 0)
    {
        const int32 Count = FMath::Min(Needed,512);
        Synth.Render(Controls,Samples,Count);
        Wave->QueueAudio(reinterpret_cast<const uint8*>(Samples),Count*sizeof(int16));
        Needed -= Count;
    }
    if (!IsPlaying()) Play();
}
