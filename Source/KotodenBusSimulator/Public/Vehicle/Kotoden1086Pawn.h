#pragma once

#include "Vehicle/BusPrototypeVehiclePawn.h"
#include "ChaosVehicleWheel.h"
#include "Kotoden1086Pawn.generated.h"

class UCameraComponent;
class UKotodenBusDisplay;
class USpotLightComponent;
class USkeletalMesh;

// Provisional vehicle calibration. Wheel, engine and drivetrain settings remain editable in a Blueprint.
UCLASS()
class KOTODENBUSSIMULATOR_API UKotoden1086FrontWheel : public UChaosVehicleWheel
{
    GENERATED_BODY()
public:
    UKotoden1086FrontWheel();
};

UCLASS()
class KOTODENBUSSIMULATOR_API UKotoden1086RearWheel : public UKotoden1086FrontWheel
{
    GENERATED_BODY()
public:
    UKotoden1086RearWheel();
};

UENUM()
enum class EBusDriveRange : uint8 { Reverse, Neutral, Drive };

UCLASS(Blueprintable)
class KOTODENBUSSIMULATOR_API AKotoden1086Pawn : public ABusPrototypeVehiclePawn
{
    GENERATED_BODY()

public:
    AKotoden1086Pawn();
    FString GetStatusText() const;

protected:
    virtual void PreRegisterAllComponents() override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    virtual void ApplyDriveAndBrake(const FBusDriverInputState& Input, float BrakeCommand) override;
    virtual void UnPossessed() override;
    virtual void PawnClientRestart() override;
    virtual void CalcCamera(float DeltaTime, FMinimalViewInfo& OutResult) override;

private:
    void SelectRange(EBusDriveRange NewRange);
    void SelectDrive() { SelectRange(EBusDriveRange::Drive); }
    void SelectNeutral() { SelectRange(EBusDriveRange::Neutral); }
    void SelectReverse() { SelectRange(EBusDriveRange::Reverse); }
    void ToggleCamera();
    void SetCabCursor(bool bEnabled);
    void ToggleParking();
    void ToggleFrontDoor();
    void ToggleMiddleDoor();
    void ToggleLights();
    void SignalLeft();
    void SignalRight();
    void ClickCockpit();

    // Blueprint class default saved by the importer, applied before Chaos creates its vehicle.
    UPROPERTY(EditDefaultsOnly, Category="Bus")
    TObjectPtr<USkeletalMesh> BusMeshAsset;

    UPROPERTY(VisibleAnywhere, Category="Bus")
    TObjectPtr<UCameraComponent> CabCamera;
    UPROPERTY(VisibleAnywhere, Category="Bus")
    TObjectPtr<UKotodenBusDisplay> Display;
    UPROPERTY(VisibleAnywhere, Category="Bus")
    TObjectPtr<USpotLightComponent> LeftHeadlamp;
    UPROPERTY(VisibleAnywhere, Category="Bus")
    TObjectPtr<USpotLightComponent> RightHeadlamp;

    UPROPERTY(EditDefaultsOnly, Category="Bus", meta=(ClampMin="0.1", Units="s"))
    float DoorTravelSeconds = 1.4f;
    UPROPERTY(EditDefaultsOnly, Category="Bus", meta=(ClampMin="0.1", Units="s"))
    float SignalPeriodSeconds = 0.8f;

    EBusDriveRange Range = EBusDriveRange::Neutral;
    bool bParking = true;
    bool bFrontOpen = false;
    bool bMiddleOpen = false;
    bool bLamps = false;
    int32 SignalDirection = 0; // -1 left / +1 right
    float FrontDoor = 0.0f;
    float MiddleDoor = 0.0f;
    float SignalTime = 0.0f;
    bool bCabView = true;
    float CabYaw = -10.0f;
    float CabPitch = -14.0f;
    float DriverSteer = 0.0f;
    float DriverThrottle = 0.0f;
    float AppliedBrake = 0.0f;
};
