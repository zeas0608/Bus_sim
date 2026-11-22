#pragma once

#include "WheeledVehiclePawn.h"
#include "BusPrototypeVehiclePawn.generated.h"

class UCameraComponent;
class USpringArmComponent;

// Four-wheel Chaos test vehicle. The Blueprint supplies the skeletal mesh and wheel setup.
UCLASS()
class KOTODENBUSSIMULATOR_API ABusPrototypeVehiclePawn : public AWheeledVehiclePawn
{
    GENERATED_BODY()

public:
    ABusPrototypeVehiclePawn();

    float GetServiceBrakeCommand() const { return ServiceBrakeCommand; }
    float GetForwardSpeedKmh() const;

protected:
    virtual void Tick(float DeltaSeconds) override;
    virtual void UnPossessed() override;

private:
    UPROPERTY(VisibleAnywhere, Category = "Prototype Camera")
    TObjectPtr<USpringArmComponent> ChaseArm;

    UPROPERTY(VisibleAnywhere, Category = "Prototype Camera")
    TObjectPtr<UCameraComponent> ChaseCamera;

    // Provisional normalized command change per second. Tune in the pawn Blueprint.
    UPROPERTY(EditDefaultsOnly, Category = "Prototype Brake", meta = (ClampMin = "0.01"))
    float BrakeRisePerSecond = 2.0f;

    UPROPERTY(EditDefaultsOnly, Category = "Prototype Brake", meta = (ClampMin = "0.01"))
    float BrakeFallPerSecond = 3.0f;

    float ServiceBrakeCommand = 0.0f;
};
