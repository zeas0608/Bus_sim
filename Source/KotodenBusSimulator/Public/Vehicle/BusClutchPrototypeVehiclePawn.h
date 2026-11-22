#pragma once

#include "Vehicle/BusPrototypeVehiclePawn.h"
#include "BusClutchPrototypeVehiclePawn.generated.h"

class UChaosWheeledVehicleMovementComponent;

// Opt-in P0-4B vehicle. Keep the P0-3 Blueprint on the original pawn class.
UCLASS(Blueprintable)
class KOTODENBUSSIMULATOR_API ABusClutchPrototypeVehiclePawn : public ABusPrototypeVehiclePawn
{
    GENERATED_BODY()

public:
    ABusClutchPrototypeVehiclePawn();

    bool AreExternalCommandsEnabled() const { return bExternalCommandsEnabled; }
    float GetClutchEngagement() const { return ClutchEngagement; }
    float GetEngineTorqueCommandNm() const { return EngineTorqueCommandNm; }
    float GetDriveTorqueCommandNm(int32 WheelIndex) const;
    float GetBrakeTorqueCommandNm() const { return BrakeTorquePerWheelNm; }

protected:
    virtual void PreRegisterAllComponents() override;
    virtual void ApplyDriveAndBrake(const FBusDriverInputState& Input, float BrakeCommand) override;
    virtual void UnPossessed() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UChaosWheeledVehicleMovementComponent& GetWheeledMovement() const;
    void WriteWheelTorques();
    void ClearWheelTorques();

    UPROPERTY(EditDefaultsOnly, Category = "Clutch Prototype", meta = (ClampMin = "0", ClampMax = "3"))
    int32 RearLeftWheelIndex = 2;

    UPROPERTY(EditDefaultsOnly, Category = "Clutch Prototype", meta = (ClampMin = "0", ClampMax = "3"))
    int32 RearRightWheelIndex = 3;

    // Provisional values for the four-wheel test vehicle.
    UPROPERTY(EditDefaultsOnly, Category = "Clutch Prototype", meta = (ClampMin = "0.0"))
    float MaxEngineTorqueNm = 250.0f;

    UPROPERTY(EditDefaultsOnly, Category = "Clutch Prototype", meta = (ClampMin = "0.0"))
    float FixedTotalReduction = 4.0f;

    UPROPERTY(EditDefaultsOnly, Category = "Clutch Prototype", meta = (ClampMin = "0.0"))
    float MaxBrakeTorquePerWheelNm = 1200.0f;

    bool bExternalCommandsEnabled = false;
    float ClutchEngagement = 0.0f;
    float EngineTorqueCommandNm = 0.0f;
    float DriveTorquePerRearWheelNm = 0.0f;
    float BrakeTorquePerWheelNm = 0.0f;
};
