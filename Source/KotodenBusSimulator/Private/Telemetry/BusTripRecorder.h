#pragma once

#include "Components/ActorComponent.h"
#include "Serialization/Archive.h"
#include "BusTripRecorder.generated.h"

struct FBusDriveReading
{
    FString Mode;
    FString Engine;
    float Rpm, SpeedMS, Clutch, Engagement, SlipRPM, Throttle, Brake, Steer, FrontDoor, MiddleDoor;
    int32 Gear;
    bool bManual, bPark, bFault, bHeadlights, bCab;
    int32 Turn;
    float YawDeg;
    struct FWheelReading
    {
        bool bValid;
        float DriveCmd, BrakeCmd, Drive, Brake;
    };
    FWheelReading Wheels[4];
};

UCLASS()
class UBusTripRecorder : public UActorComponent
{
    GENERATED_BODY()
public:
    void Toggle();
    bool IsRecording() const { return Writer.IsValid(); }
    void Sample(float Dt, const FBusDriveReading& Reading);
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    void Close();
    void Flush();
    TUniquePtr<FArchive> Writer;
    FString Buffer;
    double Elapsed = 0;
    double NextSample = 0;
    bool bFaultSinceSample = false;
};
