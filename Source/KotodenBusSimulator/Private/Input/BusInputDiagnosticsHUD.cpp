#include "BusInputDiagnosticsHUD.h"

#include "Input/BusInputPlayerController.h"
#include "Vehicle/BusPrototypeVehiclePawn.h"

void ABusInputDiagnosticsHUD::DrawHUD()
{
    Super::DrawHUD();

    const ABusInputPlayerController* Controller = Cast<ABusInputPlayerController>(GetOwningPlayerController());
    if (!Canvas || !Controller)
    {
        return;
    }

    const FBusDriverInputState Input = Controller->GetDriverInputState();
    const ABusPrototypeVehiclePawn* Vehicle = Cast<ABusPrototypeVehiclePawn>(Controller->GetPawn());
    const FString Lines[] = {
        Vehicle ? TEXT("P0-3 Chaos / F310") : TEXT("P0-2 F310 / XInput"),
        FString::Printf(TEXT("RT throttle: %.3f   LT clutch: %.3f"), Input.Throttle, Input.Clutch),
        FString::Printf(TEXT("Left X steering: %+.3f"), Input.Steering),
        FString::Printf(TEXT("Right X: %+.3f   Right Y: %+.3f"), Input.RightStickX, Input.RightStickY),
        FString::Printf(TEXT("A brake: %s   LB down: %s   RB up: %s"),
            Input.bBrakeHeld ? TEXT("ON") : TEXT("OFF"),
            Input.bGearDownHeld ? TEXT("ON") : TEXT("OFF"),
            Input.bGearUpHeld ? TEXT("ON") : TEXT("OFF"))
    };

    constexpr float LeftMargin = 24.0f;
    constexpr float LineHeight = 20.0f;
    float Y = 48.0f;
    for (const FString& Line : Lines)
    {
        DrawText(Line, FLinearColor::Cyan, LeftMargin, Y);
        Y += LineHeight;
    }

    if (Vehicle)
    {
        DrawText(FString::Printf(TEXT("Forward speed: %+.1f km/h   Service brake: %.3f"),
            Vehicle->GetForwardSpeedKmh(), Vehicle->GetServiceBrakeCommand()),
            FLinearColor::Cyan, LeftMargin, Y);
    }
}
