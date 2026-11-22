#include "BusInputDiagnosticsHUD.h"

#include "Input/BusInputPlayerController.h"

void ABusInputDiagnosticsHUD::DrawHUD()
{
    Super::DrawHUD();

    const ABusInputPlayerController* Controller = Cast<ABusInputPlayerController>(GetOwningPlayerController());
    if (!Canvas || !Controller)
    {
        return;
    }

    const FBusDriverInputState Input = Controller->GetDriverInputState();
    const FString Lines[] = {
        TEXT("P0-2 F310 / XInput"),
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
}
