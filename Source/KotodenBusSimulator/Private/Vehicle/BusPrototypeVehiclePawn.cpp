#include "Vehicle/BusPrototypeVehiclePawn.h"

#include "Camera/CameraComponent.h"
#include "ChaosVehicleMovementComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Input/BusInputPlayerController.h"

ABusPrototypeVehiclePawn::ABusPrototypeVehiclePawn()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PrePhysics;

    // Keep the service brake proportional and prevent A from requesting reverse.
    GetVehicleMovementComponent()->bReverseAsBrake = false;

    ChaseArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("ChaseArm"));
    ChaseArm->SetupAttachment(GetMesh());
    ChaseArm->SetRelativeLocation(FVector(0.0, 0.0, 115.0));
    ChaseArm->SetRelativeRotation(FRotator(-12.0, 0.0, 0.0));
    ChaseArm->TargetArmLength = 600.0f; // cm
    ChaseArm->bUsePawnControlRotation = false;
    ChaseArm->bInheritPitch = false;
    ChaseArm->bInheritRoll = false;

    ChaseCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("ChaseCamera"));
    ChaseCamera->SetupAttachment(ChaseArm, USpringArmComponent::SocketName);
}

void ABusPrototypeVehiclePawn::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    const ABusInputPlayerController* Driver = Cast<ABusInputPlayerController>(GetController());
    if (!Driver)
    {
        return;
    }

    const FBusDriverInputState Input = Driver->GetDriverInputState();
    const float BrakeRate = Input.bBrakeHeld ? BrakeRisePerSecond : -BrakeFallPerSecond;
    ServiceBrakeCommand = FMath::Clamp(ServiceBrakeCommand + BrakeRate * DeltaSeconds, 0.0f, 1.0f);

    GetVehicleMovementComponent()->SetSteeringInput(Input.Steering);
    ApplyDriveAndBrake(Input, ServiceBrakeCommand);
}

void ABusPrototypeVehiclePawn::ApplyDriveAndBrake(const FBusDriverInputState& Input, float BrakeCommand)
{
    UChaosVehicleMovementComponent* Movement = GetVehicleMovementComponent();
    Movement->SetThrottleInput(Input.Throttle);
    Movement->SetBrakeInput(BrakeCommand);
}

void ABusPrototypeVehiclePawn::UnPossessed()
{
    UChaosVehicleMovementComponent* Movement = GetVehicleMovementComponent();
    Movement->SetThrottleInput(0.0f);
    Movement->SetSteeringInput(0.0f);
    Movement->SetBrakeInput(0.0f);
    ServiceBrakeCommand = 0.0f;
    Super::UnPossessed();
}

float ABusPrototypeVehiclePawn::GetForwardSpeedKmh() const
{
    constexpr float CmPerSecondToKmh = 0.036f;
    return GetVehicleMovementComponent()->GetForwardSpeed() * CmPerSecondToKmh;
}
