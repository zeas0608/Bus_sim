#pragma once

#include "GameFramework/HUD.h"
#include "BusInputDiagnosticsHUD.generated.h"

UCLASS()
class ABusInputDiagnosticsHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;
};
