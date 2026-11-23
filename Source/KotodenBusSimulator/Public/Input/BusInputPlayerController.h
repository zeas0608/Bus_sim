#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "Input/BusDriverInputState.h"
#include "BusInputPlayerController.generated.h"

class UEnhancedInputLocalPlayerSubsystem;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

/**
 * P0-2: diagnostic input reader only. No vehicle movement, MT physics, or assets required.
 * Maps XInput gamepad keys to Enhanced Input actions in C++ so PIE works without .uasset setup.
 */
UCLASS()
class KOTODENBUSSIMULATOR_API ABusInputPlayerController : public APlayerController
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintPure, Category="Bus Input")
    FBusDriverInputState GetDriverInputState() const;

protected:
    virtual void SetupInputComponent() override;
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    void EnsureRuntimeMapping();

    static float NormalizeSignedAxis(float Raw, float DeadZone);
    static float NormalizeTrigger(float Raw, float DeadZone);

    void ThrottleChanged(const FInputActionValue& Value);
    void ThrottleReleased(const FInputActionValue& Value);
    void ClutchChanged(const FInputActionValue& Value);
    void ClutchReleased(const FInputActionValue& Value);
    void SteeringChanged(const FInputActionValue& Value);
    void SteeringReleased(const FInputActionValue& Value);
    void RightStickXChanged(const FInputActionValue& Value);
    void RightStickXReleased(const FInputActionValue& Value);
    void RightStickYChanged(const FInputActionValue& Value);
    void RightStickYReleased(const FInputActionValue& Value);
    void BrakePressed(const FInputActionValue& Value);
    void BrakeReleased(const FInputActionValue& Value);
    void GearDownPressed(const FInputActionValue& Value);
    void GearDownReleased(const FInputActionValue& Value);
    void GearUpPressed(const FInputActionValue& Value);
    void GearUpReleased(const FInputActionValue& Value);

    TWeakObjectPtr<UEnhancedInputLocalPlayerSubsystem> MappingSubsystem;

    UPROPERTY(Transient)
    TObjectPtr<UInputMappingContext> RuntimeMapping;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> ThrottleAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> ClutchAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> SteeringAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> RightStickXAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> RightStickYAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> BrakeAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> GearDownAction;

    UPROPERTY(Transient)
    TObjectPtr<UInputAction> GearUpAction;

    UPROPERTY(VisibleAnywhere, Category="Bus Input")
    FBusDriverInputState DriverInputState;

    UPROPERTY(EditDefaultsOnly, Category="Bus Input", meta=(ClampMin="0.0", ClampMax="0.99"))
    float StickDeadZone = 0.10f;

    UPROPERTY(EditDefaultsOnly, Category="Bus Input", meta=(ClampMin="0.0", ClampMax="0.99"))
    float TriggerDeadZone = 0.03f;
};
