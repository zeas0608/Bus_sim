#include "Input/BusInputPlayerController.h"

#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputCoreTypes.h"
#include "InputMappingContext.h"

void ABusInputPlayerController::EnsureRuntimeMapping()
{
    if (RuntimeMapping)
    {
        return;
    }

    RuntimeMapping = NewObject<UInputMappingContext>(this, TEXT("IMC_F310_Diagnostics"));

    auto MakeAxis = [this](const TCHAR* Name) -> UInputAction*
    {
        UInputAction* Action = NewObject<UInputAction>(this, FName(Name));
        Action->ValueType = EInputActionValueType::Axis1D;
        return Action;
    };

    auto MakeButton = [this](const TCHAR* Name) -> UInputAction*
    {
        UInputAction* Action = NewObject<UInputAction>(this, FName(Name));
        Action->ValueType = EInputActionValueType::Boolean;
        return Action;
    };

    ThrottleAction = MakeAxis(TEXT("IA_F310_Throttle"));
    ClutchAction = MakeAxis(TEXT("IA_F310_Clutch"));
    SteeringAction = MakeAxis(TEXT("IA_F310_Steering"));
    RightStickXAction = MakeAxis(TEXT("IA_F310_RightStickX"));
    RightStickYAction = MakeAxis(TEXT("IA_F310_RightStickY"));
    BrakeAction = MakeButton(TEXT("IA_F310_Brake"));
    GearDownAction = MakeButton(TEXT("IA_F310_GearDown"));
    GearUpAction = MakeButton(TEXT("IA_F310_GearUp"));

    RuntimeMapping->MapKey(ThrottleAction, EKeys::Gamepad_RightTriggerAxis);
    RuntimeMapping->MapKey(ClutchAction, EKeys::Gamepad_LeftTriggerAxis);
    RuntimeMapping->MapKey(SteeringAction, EKeys::Gamepad_LeftX);
    RuntimeMapping->MapKey(RightStickXAction, EKeys::Gamepad_RightX);
    RuntimeMapping->MapKey(RightStickYAction, EKeys::Gamepad_RightY);
    RuntimeMapping->MapKey(BrakeAction, EKeys::Gamepad_FaceButton_Bottom); // F310 A
    RuntimeMapping->MapKey(GearDownAction, EKeys::Gamepad_LeftShoulder); // LB
    RuntimeMapping->MapKey(GearUpAction, EKeys::Gamepad_RightShoulder); // RB
}

void ABusInputPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    EnsureRuntimeMapping();

    UEnhancedInputComponent* EnhancedComponent = Cast<UEnhancedInputComponent>(InputComponent);
    if (!EnhancedComponent)
    {
        UE_LOG(LogTemp, Error, TEXT("F310: Expected EnhancedInputComponent. Check Config/DefaultInput.ini."));
        return;
    }

    EnhancedComponent->BindAction(ThrottleAction, ETriggerEvent::Triggered, this, &ABusInputPlayerController::ThrottleChanged);
    EnhancedComponent->BindAction(ThrottleAction, ETriggerEvent::Completed, this, &ABusInputPlayerController::ThrottleReleased);
    EnhancedComponent->BindAction(ThrottleAction, ETriggerEvent::Canceled, this, &ABusInputPlayerController::ThrottleReleased);
    EnhancedComponent->BindAction(ClutchAction, ETriggerEvent::Triggered, this, &ABusInputPlayerController::ClutchChanged);
    EnhancedComponent->BindAction(ClutchAction, ETriggerEvent::Completed, this, &ABusInputPlayerController::ClutchReleased);
    EnhancedComponent->BindAction(ClutchAction, ETriggerEvent::Canceled, this, &ABusInputPlayerController::ClutchReleased);
    EnhancedComponent->BindAction(SteeringAction, ETriggerEvent::Triggered, this, &ABusInputPlayerController::SteeringChanged);
    EnhancedComponent->BindAction(SteeringAction, ETriggerEvent::Completed, this, &ABusInputPlayerController::SteeringReleased);
    EnhancedComponent->BindAction(SteeringAction, ETriggerEvent::Canceled, this, &ABusInputPlayerController::SteeringReleased);
    EnhancedComponent->BindAction(RightStickXAction, ETriggerEvent::Triggered, this, &ABusInputPlayerController::RightStickXChanged);
    EnhancedComponent->BindAction(RightStickXAction, ETriggerEvent::Completed, this, &ABusInputPlayerController::RightStickXReleased);
    EnhancedComponent->BindAction(RightStickXAction, ETriggerEvent::Canceled, this, &ABusInputPlayerController::RightStickXReleased);
    EnhancedComponent->BindAction(RightStickYAction, ETriggerEvent::Triggered, this, &ABusInputPlayerController::RightStickYChanged);
    EnhancedComponent->BindAction(RightStickYAction, ETriggerEvent::Completed, this, &ABusInputPlayerController::RightStickYReleased);
    EnhancedComponent->BindAction(RightStickYAction, ETriggerEvent::Canceled, this, &ABusInputPlayerController::RightStickYReleased);

    EnhancedComponent->BindAction(BrakeAction, ETriggerEvent::Started, this, &ABusInputPlayerController::BrakePressed);
    EnhancedComponent->BindAction(BrakeAction, ETriggerEvent::Completed, this, &ABusInputPlayerController::BrakeReleased);
    EnhancedComponent->BindAction(BrakeAction, ETriggerEvent::Canceled, this, &ABusInputPlayerController::BrakeReleased);
    EnhancedComponent->BindAction(GearDownAction, ETriggerEvent::Started, this, &ABusInputPlayerController::GearDownPressed);
    EnhancedComponent->BindAction(GearDownAction, ETriggerEvent::Completed, this, &ABusInputPlayerController::GearDownReleased);
    EnhancedComponent->BindAction(GearDownAction, ETriggerEvent::Canceled, this, &ABusInputPlayerController::GearDownReleased);
    EnhancedComponent->BindAction(GearUpAction, ETriggerEvent::Started, this, &ABusInputPlayerController::GearUpPressed);
    EnhancedComponent->BindAction(GearUpAction, ETriggerEvent::Completed, this, &ABusInputPlayerController::GearUpReleased);
    EnhancedComponent->BindAction(GearUpAction, ETriggerEvent::Canceled, this, &ABusInputPlayerController::GearUpReleased);
}

void ABusInputPlayerController::BeginPlay()
{
    Super::BeginPlay();

    if (!IsLocalController())
    {
        return;
    }

    EnsureRuntimeMapping();
    if (ULocalPlayer* LocalPlayer = GetLocalPlayer())
    {
        if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
                ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(LocalPlayer))
        {
            Subsystem->AddMappingContext(RuntimeMapping, 0);
            MappingSubsystem = Subsystem;
            UE_LOG(LogTemp, Log, TEXT("F310: Enhanced Input diagnostic mapping activated."));
        }
        else
        {
            UE_LOG(LogTemp, Error, TEXT("F310: Enhanced Input local player subsystem not found."));
        }
    }
}

void ABusInputPlayerController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (UEnhancedInputLocalPlayerSubsystem* Subsystem = MappingSubsystem.Get())
    {
        Subsystem->RemoveMappingContext(RuntimeMapping);
    }
    DriverInputState = {};
    Super::EndPlay(EndPlayReason);
}

float ABusInputPlayerController::NormalizeSignedAxis(float Raw, float DeadZone)
{
    DeadZone = FMath::Clamp(DeadZone, 0.0f, 0.99f);
    const float Clamped = FMath::Clamp(Raw, -1.0f, 1.0f);
    const float Magnitude = FMath::Abs(Clamped);
    if (Magnitude <= DeadZone)
    {
        return 0.0f;
    }
    return FMath::Sign(Clamped) * (Magnitude - DeadZone) / (1.0f - DeadZone);
}

float ABusInputPlayerController::NormalizeTrigger(float Raw, float DeadZone)
{
    DeadZone = FMath::Clamp(DeadZone, 0.0f, 0.99f);
    const float Clamped = FMath::Clamp(Raw, 0.0f, 1.0f);
    return Clamped <= DeadZone ? 0.0f : (Clamped - DeadZone) / (1.0f - DeadZone);
}

void ABusInputPlayerController::ThrottleChanged(const FInputActionValue& Value) { DriverInputState.Throttle = NormalizeTrigger(Value.Get<float>(), TriggerDeadZone); }
void ABusInputPlayerController::ThrottleReleased(const FInputActionValue&) { DriverInputState.Throttle = 0.0f; }
void ABusInputPlayerController::ClutchChanged(const FInputActionValue& Value) { DriverInputState.Clutch = NormalizeTrigger(Value.Get<float>(), TriggerDeadZone); }
void ABusInputPlayerController::ClutchReleased(const FInputActionValue&) { DriverInputState.Clutch = 0.0f; }
void ABusInputPlayerController::SteeringChanged(const FInputActionValue& Value) { DriverInputState.Steering = NormalizeSignedAxis(Value.Get<float>(), StickDeadZone); }
void ABusInputPlayerController::SteeringReleased(const FInputActionValue&) { DriverInputState.Steering = 0.0f; }
void ABusInputPlayerController::RightStickXChanged(const FInputActionValue& Value) { DriverInputState.RightStickX = NormalizeSignedAxis(Value.Get<float>(), StickDeadZone); }
void ABusInputPlayerController::RightStickXReleased(const FInputActionValue&) { DriverInputState.RightStickX = 0.0f; }
void ABusInputPlayerController::RightStickYChanged(const FInputActionValue& Value) { DriverInputState.RightStickY = NormalizeSignedAxis(Value.Get<float>(), StickDeadZone); }
void ABusInputPlayerController::RightStickYReleased(const FInputActionValue&) { DriverInputState.RightStickY = 0.0f; }
void ABusInputPlayerController::BrakePressed(const FInputActionValue&) { DriverInputState.bBrakeHeld = true; }
void ABusInputPlayerController::BrakeReleased(const FInputActionValue&) { DriverInputState.bBrakeHeld = false; }
void ABusInputPlayerController::GearDownPressed(const FInputActionValue&) { DriverInputState.bGearDownHeld = true; }
void ABusInputPlayerController::GearDownReleased(const FInputActionValue&) { DriverInputState.bGearDownHeld = false; }
void ABusInputPlayerController::GearUpPressed(const FInputActionValue&) { DriverInputState.bGearUpHeld = true; }
void ABusInputPlayerController::GearUpReleased(const FInputActionValue&) { DriverInputState.bGearUpHeld = false; }
