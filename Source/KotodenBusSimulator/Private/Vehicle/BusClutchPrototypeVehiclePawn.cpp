#include "Vehicle/BusClutchPrototypeVehiclePawn.h"

#include "ChaosVehicleWheel.h"
#include "ChaosWheeledVehicleMovementComponent.h"
#include "Input/BusDriverInputState.h"

ABusClutchPrototypeVehiclePawn::ABusClutchPrototypeVehiclePawn()
{
    GetWheeledMovement().bMechanicalSimEnabled = false;
}

void ABusClutchPrototypeVehiclePawn::PreRegisterAllComponents()
{
    // A reparented Blueprint may have saved true on the inherited movement component.
    // Make this choice before registration can create the Chaos vehicle.
    GetWheeledMovement().bMechanicalSimEnabled = false;
    Super::PreRegisterAllComponents();
}

UChaosWheeledVehicleMovementComponent& ABusClutchPrototypeVehiclePawn::GetWheeledMovement() const
{
    return *CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
}

void ABusClutchPrototypeVehiclePawn::ApplyDriveAndBrake(const FBusDriverInputState& Input, float BrakeCommand)
{
    constexpr int32 ExpectedWheels = 4;
    const UChaosWheeledVehicleMovementComponent& Movement = GetWheeledMovement();
    bExternalCommandsEnabled =
        !Movement.bMechanicalSimEnabled && Movement.GetNumWheels() == ExpectedWheels
        && RearLeftWheelIndex >= 0 && RearLeftWheelIndex < ExpectedWheels
        && RearRightWheelIndex >= 0 && RearRightWheelIndex < ExpectedWheels
        && RearLeftWheelIndex != RearRightWheelIndex;

    ClutchEngagement = 1.0f - FMath::Clamp(Input.Clutch, 0.0f, 1.0f);
    EngineTorqueCommandNm = FMath::Clamp(Input.Throttle, 0.0f, 1.0f) * MaxEngineTorqueNm;
    DriveTorquePerRearWheelNm = bExternalCommandsEnabled
        ? EngineTorqueCommandNm * ClutchEngagement * FixedTotalReduction * 0.5f : 0.0f;
    BrakeTorquePerWheelNm = bExternalCommandsEnabled ? BrakeCommand * MaxBrakeTorquePerWheelNm : 0.0f;
    WriteWheelTorques();
}

float ABusClutchPrototypeVehiclePawn::GetDriveTorqueCommandNm(int32 WheelIndex) const
{
    return (WheelIndex == RearLeftWheelIndex || WheelIndex == RearRightWheelIndex)
        ? DriveTorquePerRearWheelNm : 0.0f;
}

void ABusClutchPrototypeVehiclePawn::WriteWheelTorques()
{
    UChaosWheeledVehicleMovementComponent& Movement = GetWheeledMovement();
    const int32 WheelCount = Movement.GetNumWheels();
    for (int32 WheelIndex = 0; WheelIndex < WheelCount; ++WheelIndex)
    {
        // Override retains both values until overwritten, including explicit zero commands.
        Movement.SetDriveTorque(GetDriveTorqueCommandNm(WheelIndex), WheelIndex);
        Movement.SetBrakeTorque(BrakeTorquePerWheelNm, WheelIndex);
        if (bExternalCommandsEnabled)
        {
            Movement.SetTorqueCombineMethod(ETorqueCombineMethod::Override, WheelIndex);
        }
    }
}

void ABusClutchPrototypeVehiclePawn::ClearWheelTorques()
{
    bExternalCommandsEnabled = false;
    ClutchEngagement = 0.0f;
    EngineTorqueCommandNm = 0.0f;
    DriveTorquePerRearWheelNm = 0.0f;
    BrakeTorquePerWheelNm = 0.0f;
    WriteWheelTorques();
}

void ABusClutchPrototypeVehiclePawn::UnPossessed()
{
    ClearWheelTorques();
    Super::UnPossessed();
}

void ABusClutchPrototypeVehiclePawn::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    ClearWheelTorques();
    Super::EndPlay(EndPlayReason);
}
