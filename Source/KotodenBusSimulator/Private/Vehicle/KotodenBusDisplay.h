#pragma once

#include "Components/ActorComponent.h"
#include "KotodenBusDisplay.generated.h"

class UChaosWheeledVehicleMovementComponent;
class UMaterialInstanceDynamic;
class UPoseableMeshComponent;
class USkeletalMeshComponent;

// The hidden chassis remains the Chaos skeletal body. This render-only skin animates rigid parts.
UCLASS()
class UKotodenBusDisplay : public UActorComponent
{
    GENERATED_BODY()

public:
    void Initialize(USkeletalMeshComponent& Chassis);
    bool GetControlLocation(FName Bone, FVector& Location) const;
    void PoseWheels(const UChaosWheeledVehicleMovementComponent& Movement);
    void PoseCab(float Steer, float Kmh, float Rpm, float FrontDoor, float MiddleDoor,
                 float Throttle, float Brake, int32 SelectedRange);
    void PoseSwitches(bool bFront, bool bMiddle, bool bPark, bool bLights, int32 Turn);
    void SetLights(bool bLowBeam, bool bLeft, bool bRight, bool bBraking);

private:
    void Pose(FName Bone, const FQuat& Rotation, const FVector& Offset = FVector::ZeroVector);
    UPROPERTY(Transient)
    TObjectPtr<UPoseableMeshComponent> Skin;
    int32 PreviousLampState = INDEX_NONE;
    TMap<FName, FTransform> RestPose;
    UPROPERTY(Transient)
    TMap<FName, TObjectPtr<UMaterialInstanceDynamic>> Lamps;
};
