#pragma once
#include "Components/AudioComponent.h"
#include "BusSoundGenerator.h"
#include "BusDriveAudio.generated.h"

class USoundWaveProcedural;

UCLASS()
class UBusDriveAudio : public UAudioComponent
{
    GENERATED_BODY()
public:
    void Update(const BusAudio::Controls& Controls);
private:
    UPROPERTY(Transient)
    TObjectPtr<USoundWaveProcedural> Wave;
    BusAudio::Generator Synth;
};
