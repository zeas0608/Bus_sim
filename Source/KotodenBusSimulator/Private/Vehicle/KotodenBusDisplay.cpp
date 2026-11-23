#include "KotodenBusDisplay.h"

#include "ChaosWheeledVehicleMovementComponent.h"
#include "ChaosVehicleWheel.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "GameFramework/Actor.h"
#include "Engine/SkeletalMesh.h"
#include "Materials/MaterialInstanceDynamic.h"

void UKotodenBusDisplay::Initialize(USkeletalMeshComponent& Chassis)
{
    if (!Chassis.GetSkeletalMeshAsset()) return;
    Skin = NewObject<UPoseableMeshComponent>(GetOwner(), TEXT("AnimatedBusBody"));
    Skin->SetupAttachment(&Chassis);
    Skin->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Skin->SetGenerateOverlapEvents(false);
    Skin->SetSkinnedAssetAndUpdate(Chassis.GetSkeletalMeshAsset());
    GetOwner()->AddInstanceComponent(Skin);
    Skin->RegisterComponent();
    for (int32 I = 0; I < Skin->GetNumBones(); ++I)
    {
        const FName Bone = Skin->GetBoneName(I);
        RestPose.Add(Bone, Skin->GetBoneTransformByName(Bone, EBoneSpaces::ComponentSpace));
    }
    for (int32 I = 0; I < Chassis.GetNumMaterials(); ++I) Skin->SetMaterial(I, Chassis.GetMaterial(I));
    const FName Slots[] = { TEXT("HeadlampLens"), TEXT("TailLens"), TEXT("SignalLeft"), TEXT("SignalRight") };
    for (FName Slot : Slots)
    {
        const int32 Index = Skin->GetMaterialIndex(Slot);
        if (Index != INDEX_NONE)
            Lamps.Add(Slot, Skin->CreateDynamicMaterialInstance(Index));
    }
    Chassis.SetVisibility(false, false);
}

bool UKotodenBusDisplay::GetControlLocation(FName Bone, FVector& Location) const
{
    if (!Skin || !RestPose.Contains(Bone)) return false;
    Location = Skin->GetSocketLocation(Bone);
    return true;
}

void UKotodenBusDisplay::Pose(FName Bone, const FQuat& Rotation, const FVector& Offset)
{
    const FTransform* Rest = RestPose.Find(Bone);
    if (!Rest) return;
    FTransform Transform = *Rest;
    Transform.SetRotation(Rotation * Rest->GetRotation());
    Transform.AddToTranslation(Offset);
    Skin->SetBoneTransformByName(Bone, Transform, EBoneSpaces::ComponentSpace);
}

void UKotodenBusDisplay::PoseWheels(const UChaosWheeledVehicleMovementComponent& Movement)
{
    for (int32 I = 0; I < Movement.Wheels.Num(); ++I)
    {
        const UChaosVehicleWheel* Wheel = Movement.Wheels[I];
        if (!Wheel || !Movement.WheelSetups.IsValidIndex(I) || I >= Movement.GetNumWheels()
            || !Movement.GetWheelState(I).bIsValid) continue;
        const FRotator Rotation(Wheel->GetRotationAngle(), Wheel->GetSteerAngle(), 0);
        Pose(Movement.WheelSetups[I].BoneName, Rotation.Quaternion(),
            -Wheel->GetSuspensionAxis() * Wheel->GetSuspensionOffset());
    }
}

void UKotodenBusDisplay::PoseCab(float Steer, float Kmh, float Rpm, float FrontDoor, float MiddleDoor,
                                 float Throttle, float Brake, int32 SelectedRange)
{
    const FVector GaugeAxis = FVector(-0.94, 0, 0.342).GetSafeNormal();
    Pose(TEXT("needle_speed"), FQuat(GaugeAxis, FMath::DegreesToRadians(270.0f * FMath::Clamp(Kmh / 120.0f, 0.0f, 1.0f))));
    Pose(TEXT("needle_rpm"), FQuat(GaugeAxis, FMath::DegreesToRadians(270.0f * FMath::Clamp(Rpm / 3000.0f, 0.0f, 1.0f))));
    Pose(TEXT("steering"), FQuat(FVector(-0.54, 0, 0.842).GetSafeNormal(), FMath::DegreesToRadians(Steer * 540.0f)));
    Pose(TEXT("door_front_A"), FRotator(0, -85.0f * FrontDoor, 0).Quaternion());
    Pose(TEXT("door_front_B"), FRotator(0, 85.0f * FrontDoor, 0).Quaternion());
    Pose(TEXT("door_mid_A"), FQuat::Identity, FVector(55, 4, 0) * MiddleDoor);
    Pose(TEXT("door_mid_B"), FQuat::Identity, FVector(-55, 4, 0) * MiddleDoor);
    Pose(TEXT("selector"), FQuat::Identity, FVector(3.84, 0, 1.44) * SelectedRange);
    Pose(TEXT("pedal_throttle"), FRotator(-Throttle * 12.0f, 0, 0).Quaternion());
    Pose(TEXT("pedal_brake"), FRotator(-Brake * 12.0f, 0, 0).Quaternion());
}

void UKotodenBusDisplay::PoseSwitches(bool bFront, bool bMiddle, bool bPark, bool bLights, int32 Turn)
{
    // A depressed key travels into the inclined console in chassis space (cm).
    const FVector Down(0.12, 0.0, -0.32);
    Pose(TEXT("switch_front"), FQuat::Identity, bFront ? Down : FVector::ZeroVector);
    Pose(TEXT("switch_mid"), FQuat::Identity, bMiddle ? Down : FVector::ZeroVector);
    Pose(TEXT("switch_park"), FQuat::Identity, bPark ? Down : FVector::ZeroVector);
    Pose(TEXT("switch_lights"), FQuat::Identity, bLights ? Down : FVector::ZeroVector);
    Pose(TEXT("switch_left"), FQuat::Identity, Turn < 0 ? Down : FVector::ZeroVector);
    Pose(TEXT("switch_right"), FQuat::Identity, Turn > 0 ? Down : FVector::ZeroVector);
}

void UKotodenBusDisplay::SetLights(bool bLowBeam, bool bLeft, bool bRight, bool bBraking)
{
    const int32 State = (bLowBeam ? 1 : 0) | (bLeft ? 2 : 0) | (bRight ? 4 : 0) | (bBraking ? 8 : 0);
    if (State == PreviousLampState) return;
    PreviousLampState = State;
    auto SetGlow = [this](FName Slot, float Glow)
    {
        if (auto* Material = Lamps.Find(Slot); Material && *Material)
            (*Material)->SetScalarParameterValue(TEXT("Glow"), Glow);
    };
    SetGlow(TEXT("HeadlampLens"), bLowBeam ? 7.f : 0.f);
    SetGlow(TEXT("SignalLeft"), bLeft ? 7.f : 0.f);
    SetGlow(TEXT("SignalRight"), bRight ? 7.f : 0.f);
    SetGlow(TEXT("TailLens"), bBraking ? 6.f : (bLowBeam ? 1.5f : 0.f));
}
