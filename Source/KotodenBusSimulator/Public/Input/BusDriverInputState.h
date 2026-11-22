#pragma once

#include "CoreMinimal.h"
#include "BusDriverInputState.generated.h"

// Normalized values (not vehicle physics yet). Designed for later drive-by-wire integration.
USTRUCT(BlueprintType)
struct FBusDriverInputState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="Bus Input")
    float Throttle = 0.0f; // RT, 0 (released) to 1 (fully pressed)

    UPROPERTY(BlueprintReadOnly, Category="Bus Input")
    float Clutch = 0.0f; // LT, 0 (engaged pedal released) to 1 (fully depressed)

    UPROPERTY(BlueprintReadOnly, Category="Bus Input")
    float Steering = 0.0f; // Left stick X, -1 to +1

    UPROPERTY(BlueprintReadOnly, Category="Bus Input")
    float RightStickX = 0.0f; // -1 to +1

    UPROPERTY(BlueprintReadOnly, Category="Bus Input")
    float RightStickY = 0.0f; // -1 to +1

    UPROPERTY(BlueprintReadOnly, Category="Bus Input")
    bool bBrakeHeld = false; // A button; P0-2 only reads the button

    UPROPERTY(BlueprintReadOnly, Category="Bus Input")
    bool bGearDownHeld = false; // LB

    UPROPERTY(BlueprintReadOnly, Category="Bus Input")
    bool bGearUpHeld = false; // RB
};
