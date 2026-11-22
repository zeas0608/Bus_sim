#include "Input/BusInputGameMode.h"

#include "GameFramework/SpectatorPawn.h"
#include "Input/BusInputPlayerController.h"

ABusInputGameMode::ABusInputGameMode()
{
    // SpectatorPawn is collision-free, so the stock Entry map's "BAD SIZE" PlayerStart
    // is not a blocker. This is strictly an input-only diagnostic map.
    DefaultPawnClass = ASpectatorPawn::StaticClass();
    PlayerControllerClass = ABusInputPlayerController::StaticClass();
}
