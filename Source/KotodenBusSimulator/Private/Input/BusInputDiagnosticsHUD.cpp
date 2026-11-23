#include "BusInputDiagnosticsHUD.h"

#include "ChaosWheeledVehicleMovementComponent.h"
#include "Input/BusInputPlayerController.h"
#include "Vehicle/BusClutchPrototypeVehiclePawn.h"
#include "Vehicle/BusPrototypeVehiclePawn.h"
#include "Vehicle/Kotoden1086Pawn.h"

void ABusInputDiagnosticsHUD::DrawHUD()
{
    Super::DrawHUD();

    const ABusInputPlayerController* Controller = Cast<ABusInputPlayerController>(GetOwningPlayerController());
    if (!Canvas || !Controller)
    {
        return;
    }

    if (const auto* Bus = Cast<AKotoden1086Pawn>(Controller->GetPawn()))
    {
        DrawText(Bus->GetStatusText(), FLinearColor::White, 18.0f, 24.0f);
        return;
    }

    const FBusDriverInputState Input = Controller->GetDriverInputState();
    const ABusPrototypeVehiclePawn* Vehicle = Cast<ABusPrototypeVehiclePawn>(Controller->GetPawn());
    const ABusClutchPrototypeVehiclePawn* ClutchVehicle = Cast<ABusClutchPrototypeVehiclePawn>(Vehicle);
    const FString Lines[] = {
        ClutchVehicle ? TEXT("P0-4B Chaos / External Clutch") :
            (Vehicle ? TEXT("P0-3 Chaos / F310") : TEXT("P0-2 F310 / XInput")),
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
        DrawText(Line, FLinearColor(0.0f, 1.0f, 1.0f, 1.0f), LeftMargin, Y);
        Y += LineHeight;
    }

    if (Vehicle)
    {
        DrawText(FString::Printf(TEXT("Forward speed: %+.1f km/h   Service brake: %.3f"),
            Vehicle->GetForwardSpeedKmh(), Vehicle->GetServiceBrakeCommand()),
            FLinearColor(0.0f, 1.0f, 1.0f, 1.0f), LeftMargin, Y);
    }

    if (!ClutchVehicle)
    {
        return;
    }

    const auto* Movement = CastChecked<UChaosWheeledVehicleMovementComponent>(ClutchVehicle->GetVehicleMovementComponent());
    Y += LineHeight;
    DrawText(FString::Printf(TEXT("Clutch engagement: %.3f   Engine command: %.1f Nm   External commands: %s"),
        ClutchVehicle->GetClutchEngagement(), ClutchVehicle->GetEngineTorqueCommandNm(),
        ClutchVehicle->AreExternalCommandsEnabled() ? TEXT("ON") : TEXT("BLOCKED")),
        FLinearColor(0.0f, 1.0f, 1.0f, 1.0f), LeftMargin, Y);

    for (int32 WheelIndex = 0; WheelIndex < Movement->GetNumWheels(); ++WheelIndex)
    {
        const FWheelStatus& Wheel = Movement->GetWheelState(WheelIndex);
        const FString PhysicsSample = Wheel.bIsValid
            ? FString::Printf(TEXT("%.1f / %.1f   %s"), Wheel.DriveTorque, Wheel.BrakeTorque,
                Wheel.bInContact ? TEXT("ground") : TEXT("air"))
            : TEXT("pending");
        Y += LineHeight;
        DrawText(FString::Printf(TEXT("Wheel %d (Nm) drive/brake: cmd %.1f / %.1f | Chaos %s"),
            WheelIndex, ClutchVehicle->GetDriveTorqueCommandNm(WheelIndex),
            ClutchVehicle->GetBrakeTorqueCommandNm(), *PhysicsSample), FLinearColor(0.0f, 1.0f, 1.0f, 1.0f), LeftMargin, Y);
    }
}
