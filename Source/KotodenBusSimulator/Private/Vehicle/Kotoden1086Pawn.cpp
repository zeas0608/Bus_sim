#include "Vehicle/Kotoden1086Pawn.h"

#include "Camera/CameraComponent.h"
#include "ChaosWheeledVehicleMovementComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Misc/ConfigCacheIni.h"
#include "PhysicsEngine/BodyInstance.h"
#include "GameFramework/SpringArmComponent.h"
#include "Input/BusInputPlayerController.h"
#include "InputCoreTypes.h"
#include "KotodenBusDisplay.h"
#include "Telemetry/BusTripRecorder.h"

namespace
{
    // Absolute longitudinal speed below which the entry doors and D/R interlock allow operation.
    constexpr float StationaryKmh = 0.8f;
}

UKotoden1086FrontWheel::UKotoden1086FrontWheel()
{
    AxleType = EAxleType::Front;
    bAffectedBySteering = true;
    bAffectedByEngine = false;
    bAffectedByHandbrake = false;
    WheelRadius = 39.0f;
    WheelWidth = 22.0f;
    WheelMass = 70.0f;
    MaxSteerAngle = 43.0f;
    MaxBrakeTorque = 6800.0f;
    SpringRate = 2100.f;
    SuspensionMaxRaise = 18.0f;
    SuspensionMaxDrop = 16.0f;
    SuspensionDampingRatio = 0.7f;
}

UKotoden1086RearWheel::UKotoden1086RearWheel()
{
    AxleType = EAxleType::Rear;
    bAffectedBySteering = false;
    bAffectedByEngine = true;
    bAffectedByHandbrake = true;
    WheelWidth = 42.0f; // One equivalent contact patch per dual wheel assembly.
    WheelMass = 120.0f;
    MaxBrakeTorque = 5500.0f;
    MaxHandBrakeTorque = 10000.0f;
    SpringRate = 2700.f;
}

AKotoden1086Pawn::AKotoden1086Pawn()
{
    auto* M = CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
    // Provisional empty vehicle and powertrain defaults. See docs/1086-REFERENCES.md.
    M->Mass = 8500.0f;
    M->bEnableCenterOfMassOverride = true;
    M->CenterOfMassOverride = FVector(-35, 0, 115);
    M->InertiaTensorScale = FVector::OneVector; // Physics Asset shape supplies the tensor.
    M->ChassisWidth = 230.f;
    M->ChassisHeight = 298.f;
    M->DownforceCoefficient = 0.f;
    M->WheelSetups.SetNum(4);
    const FName Bones[] = {TEXT("wheel_FL"), TEXT("wheel_FR"), TEXT("wheel_RL"), TEXT("wheel_RR")};
    for (int32 I = 0; I < UE_ARRAY_COUNT(Bones); ++I)
    {
        M->WheelSetups[I].BoneName = Bones[I];
        M->WheelSetups[I].WheelClass = I < 2 ? UKotoden1086FrontWheel::StaticClass() : UKotoden1086RearWheel::StaticClass();
    }
    M->SteeringSetup.SteeringType = ESteeringType::Ackermann;
    M->DifferentialSetup.DifferentialType = EVehicleDifferential::RearWheelDrive;
    auto& Engine = M->EngineSetup;
    Engine.EngineIdleRPM = 650.f;
    Engine.MaxRPM = 2700.f;
    Engine.MaxTorque = 650.f;
    auto* Curve = Engine.TorqueCurve.GetRichCurve();
    Curve->Reset();
    Curve->AddKey(0.f, 0.45f);
    Curve->AddKey(650.f, 0.65f);
    Curve->AddKey(1400.f, 1.0f);
    Curve->AddKey(2100.f, 0.83f);
    Curve->AddKey(2700.f, 0.55f);

    auto& AT = M->TransmissionSetup;
    AT.bUseAutomaticGears = true;
    AT.bUseAutoReverse = false;
    AT.ForwardGearRatios = {3.49f, 1.86f, 1.41f, 1.0f, 0.75f, 0.65f};
    AT.ReverseGearRatios = {5.03f};
    AT.FinalRatio = 5.57f;
    AT.ChangeUpRPM = 2200.f;
    AT.ChangeDownRPM = 1100.f;
    AT.GearChangeTime = 0.4f;
    AT.TransmissionEfficiency = 0.90f;

    CabCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("DriverEyes"));
    CabCamera->SetupAttachment(GetMesh());
    CabCamera->SetRelativeLocation(FVector(320, 65, 186));
    CabCamera->SetRelativeRotation(FRotator(CabPitch, CabYaw, 0));
    CabCamera->FieldOfView = 90.f;
    CabCamera->bAutoActivate = false;
    Recorder = CreateDefaultSubobject<UBusTripRecorder>(TEXT("TripRecorder"));
    Display = CreateDefaultSubobject<UKotodenBusDisplay>(TEXT("BusBodyDisplay"));

    LeftHeadlamp = CreateDefaultSubobject<USpotLightComponent>(TEXT("LeftHeadlamp"));
    RightHeadlamp = CreateDefaultSubobject<USpotLightComponent>(TEXT("RightHeadlamp"));
    for (auto* Lamp : { LeftHeadlamp.Get(), RightHeadlamp.Get() })
    {
        Lamp->SetupAttachment(GetMesh());
        Lamp->SetRelativeLocation(FVector(435, Lamp == LeftHeadlamp.Get() ? -81 : 81, 80));
        Lamp->SetRelativeRotation(FRotator(-4, 0, 0));
        Lamp->SetIntensity(18000.f);
        Lamp->SetAttenuationRadius(4200.f);
        Lamp->SetOuterConeAngle(27.f);
        Lamp->SetInnerConeAngle(12.f);
        Lamp->SetVisibility(false);
    }
}

void AKotoden1086Pawn::PreRegisterAllComponents()
{
    // A generated Blueprint holds the asset on the Pawn even if its inherited component
    // template is reconstructed on compile. Resolve it before any wheel physics is created.
    USkeletalMeshComponent* Chassis = GetMesh();
    if (BusMeshAsset && Chassis && !Chassis->IsRegistered())
    {
        if (Chassis->GetSkeletalMeshAsset() != BusMeshAsset)
        {
            Chassis->SetSkeletalMeshAsset(BusMeshAsset);
        }
        Chassis->SetCollisionProfileName(TEXT("Vehicle"));
        Chassis->BodyInstance.bSimulatePhysics = true;
    }
    Super::PreRegisterAllComponents();
}

void AKotoden1086Pawn::BeginPlay()
{
    Super::BeginPlay();
    const TCHAR* Section = TEXT("Kotoden1086.VirtualMT");
    auto& Config = Manual.Setup;
    for (int32 I = 0; I < 6; ++I)
        GConfig->GetFloat(Section, *FString::Printf(TEXT("Gear%d"), I + 1), Config.Forward[I], GGameIni);
    GConfig->GetFloat(Section, TEXT("Reverse"), Config.Reverse, GGameIni);
    GConfig->GetFloat(Section, TEXT("FinalDrive"), Config.FinalDrive, GGameIni);
    GConfig->GetFloat(Section, TEXT("Inertia"), Config.Inertia, GGameIni);
    GConfig->GetFloat(Section, TEXT("PeakNm"), Config.PeakNm, GGameIni);
    GConfig->GetFloat(Section, TEXT("CapacityNm"), Config.CapacityNm, GGameIni);
    GConfig->GetFloat(Section, TEXT("Coupling"), Config.Coupling, GGameIni);
    GConfig->GetFloat(Section, TEXT("IdleRPM"), Config.IdleRPM, GGameIni);
    GConfig->GetFloat(Section, TEXT("LimitRPM"), Config.LimitRPM, GGameIni);
    Display->Initialize(*GetMesh());
    if (auto* Arm = FindComponentByClass<USpringArmComponent>())
    {
        Arm->TargetArmLength = 1250.f;
        Arm->SetRelativeLocation(FVector(0,0,240));
    }
    auto* Movement = GetVehicleMovementComponent();
    Movement->SetUseAutomaticGears(false);
    Movement->SetTargetGear(0, true);
    Movement->SetHandbrakeInput(bParking);
}

void AKotoden1086Pawn::SetupPlayerInputComponent(UInputComponent* IC)
{
    Super::SetupPlayerInputComponent(IC);
    IC->BindKey(EKeys::K, IE_Pressed, this, &AKotoden1086Pawn::ToggleRecording);
    IC->BindKey(EKeys::T, IE_Pressed, this, &AKotoden1086Pawn::CycleMode);
    IC->BindKey(EKeys::I, IE_Pressed, this, &AKotoden1086Pawn::Ignition);
    IC->BindKey(EKeys::C, IE_Pressed, this, &AKotoden1086Pawn::ToggleCamera);
    IC->BindKey(EKeys::SpaceBar, IE_Pressed, this, &AKotoden1086Pawn::ToggleParking);
    IC->BindKey(EKeys::F, IE_Pressed, this, &AKotoden1086Pawn::ToggleFrontDoor);
    IC->BindKey(EKeys::M, IE_Pressed, this, &AKotoden1086Pawn::ToggleMiddleDoor);
    IC->BindKey(EKeys::L, IE_Pressed, this, &AKotoden1086Pawn::ToggleLights);
    IC->BindKey(EKeys::Q, IE_Pressed, this, &AKotoden1086Pawn::SignalLeft);
    IC->BindKey(EKeys::E, IE_Pressed, this, &AKotoden1086Pawn::SignalRight);
    IC->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &AKotoden1086Pawn::ClickCockpit);
    IC->BindKey(EKeys::One, IE_Pressed, this, &AKotoden1086Pawn::SelectDrive);
    IC->BindKey(EKeys::Two, IE_Pressed, this, &AKotoden1086Pawn::SelectNeutral);
    IC->BindKey(EKeys::Three, IE_Pressed, this, &AKotoden1086Pawn::SelectReverse);
}

void AKotoden1086Pawn::SelectRange(EBusDriveRange NewRange)
{
    if (Mode != EDriveMode::AT || FMath::Abs(GetForwardSpeedKmh()) > StationaryKmh || NewRange == Range) return;
    Range = NewRange;
    auto* M = GetVehicleMovementComponent();
    M->SetUseAutomaticGears(Range == EBusDriveRange::Drive);
    M->SetTargetGear(Range == EBusDriveRange::Drive ? 1 : (Range == EBusDriveRange::Reverse ? -1 : 0), true);
}

void AKotoden1086Pawn::ApplyDriveAndBrake(const FBusDriverInputState& Input, float BrakeCommand)
{
    auto* M = GetVehicleMovementComponent();
    const bool bDoorInterlock = bFrontOpen || bMiddleOpen || FrontDoor > 0.001f || MiddleDoor > 0.001f;
    DriverThrottle = Input.Throttle;
    DriverSteer = Input.Steering;
    DriverClutch = Input.Clutch;
    AppliedBrake = bDoorInterlock ? 1.f : BrakeCommand;
    if (Mode != EDriveMode::AT)
    {
        ApplyManual(Input, GetWorld()->GetDeltaSeconds(), bDoorInterlock || bParking);
        return;
    }
    if (Range == EBusDriveRange::Reverse && M->GetTargetGear() != -1) M->SetTargetGear(-1, true);
    if (Range == EBusDriveRange::Neutral && M->GetTargetGear() != 0) M->SetTargetGear(0, true);
    const bool bCanDrive = Range != EBusDriveRange::Neutral && !bParking && !bDoorInterlock;
    M->SetThrottleInput(bCanDrive ? Input.Throttle : 0.f);
    M->SetBrakeInput(AppliedBrake);
    M->SetHandbrakeInput(bParking);
}

void AKotoden1086Pawn::ToggleFrontDoor()
{
    if (FMath::Abs(GetForwardSpeedKmh()) <= StationaryKmh) bFrontOpen = !bFrontOpen;
}

void AKotoden1086Pawn::ToggleMiddleDoor()
{
    if (FMath::Abs(GetForwardSpeedKmh()) <= StationaryKmh) bMiddleOpen = !bMiddleOpen;
}

void AKotoden1086Pawn::ToggleParking()
{
    bParking = !bParking;
    GetVehicleMovementComponent()->SetHandbrakeInput(bParking);
}

void AKotoden1086Pawn::ToggleLights()
{
    bLamps = !bLamps;
    LeftHeadlamp->SetVisibility(bLamps);
    RightHeadlamp->SetVisibility(bLamps);
}

void AKotoden1086Pawn::SignalLeft()
{
    SignalDirection = SignalDirection == -1 ? 0 : -1;
    SignalTime = 0.f;
}

void AKotoden1086Pawn::SignalRight()
{
    SignalDirection = SignalDirection == 1 ? 0 : 1;
    SignalTime = 0.f;
}

void AKotoden1086Pawn::Tick(float Dt)
{
    Super::Tick(Dt);
    if (Recorder->IsRecording()) RecordDrive(Dt);
    const float DoorRate = 1.f / FMath::Max(DoorTravelSeconds, 0.1f);
    FrontDoor = FMath::FInterpConstantTo(FrontDoor, bFrontOpen ? 1.f : 0.f, Dt, DoorRate);
    MiddleDoor = FMath::FInterpConstantTo(MiddleDoor, bMiddleOpen ? 1.f : 0.f, Dt, DoorRate);
    const auto* M = CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
    Display->PoseWheels(*M);
    Display->PoseCab(DriverSteer, FMath::Abs(GetForwardSpeedKmh()), EngineRPM(),
        FrontDoor, MiddleDoor, DriverThrottle, GetServiceBrakeCommand(), Mode == EDriveMode::AT ? static_cast<int32>(Range) - 1 : 0);
    const float Period = FMath::Max(0.1f, SignalPeriodSeconds);
    SignalTime = FMath::Fmod(SignalTime + Dt, Period);
    const bool bFlash = SignalTime < Period * 0.5f;
    Display->PoseSwitches(bFrontOpen, bMiddleOpen, bParking, bLamps, SignalDirection);
    Display->SetLights(bLamps, bFlash && SignalDirection == -1, bFlash && SignalDirection == 1, AppliedBrake > 0.01f);
    if (const auto* Driver = Cast<ABusInputPlayerController>(GetController()); Driver && bCabView)
    {
        const FBusDriverInputState Input = Driver->GetDriverInputState();
        CabYaw = FMath::Clamp(CabYaw + Input.RightStickX * Dt * 75.f, -90.f, 90.f);
        CabPitch = FMath::Clamp(CabPitch + Input.RightStickY * Dt * 60.f, -55.f, 30.f);
        CabCamera->SetRelativeRotation(FRotator(CabPitch, CabYaw, 0));
    }
}

void AKotoden1086Pawn::CalcCamera(float Dt, FMinimalViewInfo& OutResult)
{
    if (bCabView) CabCamera->GetCameraView(Dt, OutResult);
    else Super::CalcCamera(Dt, OutResult);
}

void AKotoden1086Pawn::SetCabCursor(bool bEnabled)
{
    if (auto* PC = Cast<APlayerController>(GetController()); PC && PC->IsLocalController())
    {
        PC->bShowMouseCursor = bEnabled;
        if (bEnabled)
        {
            FInputModeGameAndUI Mode;
            Mode.SetHideCursorDuringCapture(false);
            PC->SetInputMode(Mode);
        }
        else PC->SetInputMode(FInputModeGameOnly());
    }
}

void AKotoden1086Pawn::ToggleCamera()
{
    bCabView = !bCabView;
    SetCabCursor(bCabView);
}

void AKotoden1086Pawn::PawnClientRestart()
{
    Super::PawnClientRestart();
    SetCabCursor(bCabView);
}

void AKotoden1086Pawn::UnPossessed()
{
    ReleaseOverride();
    Mode = EDriveMode::AT;
    Manual.Reset();
    SetCabCursor(false);
    Range = EBusDriveRange::Neutral;
    DriverSteer = 0.f;
    DriverThrottle = 0.f;
    AppliedBrake = 0.f;
    GetVehicleMovementComponent()->SetUseAutomaticGears(false);
    GetVehicleMovementComponent()->SetTargetGear(0, true);
    bParking = true;
    GetVehicleMovementComponent()->SetHandbrakeInput(true);
    Super::UnPossessed();
}

void AKotoden1086Pawn::ClickCockpit()
{
    auto* PC = Cast<APlayerController>(GetController());
    FVector Origin, Direction;
    if (!bCabView || !PC || !PC->DeprojectMousePositionToWorld(Origin, Direction)) return;
    // Pick small physical controls by their rig pivots, independent of the chassis collision hull.
    static const FName Controls[] = {TEXT("selector"), TEXT("switch_front"), TEXT("switch_mid"),
        TEXT("switch_park"), TEXT("switch_lights"), TEXT("switch_left"), TEXT("switch_right")};
    FName Picked = NAME_None;
    double BestDistance = 6.5; // cm around each control
    for (FName Bone : Controls)
    {
        FVector Target;
        if (!Display->GetControlLocation(Bone, Target)) continue;
        if (Bone == TEXT("selector")) Target += GetActorUpVector() * 5.f;
        const FVector ToTarget = Target - Origin;
        const double Depth = FVector::DotProduct(ToTarget, Direction);
        if (Depth <= 0 || Depth > 180) continue;
        const double Distance = (ToTarget - Direction * Depth).Size();
        if (Distance < BestDistance) { BestDistance = Distance; Picked = Bone; }
    }
    if (Picked == TEXT("selector"))
    {
        SelectRange(Range == EBusDriveRange::Neutral ? EBusDriveRange::Drive :
            (Range == EBusDriveRange::Drive ? EBusDriveRange::Reverse : EBusDriveRange::Neutral));
    }
    else if (Picked == TEXT("switch_front")) ToggleFrontDoor();
    else if (Picked == TEXT("switch_mid")) ToggleMiddleDoor();
    else if (Picked == TEXT("switch_park")) ToggleParking();
    else if (Picked == TEXT("switch_lights")) ToggleLights();
    else if (Picked == TEXT("switch_left")) SignalLeft();
    else if (Picked == TEXT("switch_right")) SignalRight();
}

FString AKotoden1086Pawn::GetStatusText() const
{
    const TCHAR* RangeName = Range == EBusDriveRange::Drive ? TEXT("D") : (Range == EBusDriveRange::Reverse ? TEXT("R") : TEXT("N"));
    const auto* M = CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
    const FString Notice = (Recorder->IsRecording() ? FString(TEXT("REC  ")) : FString()) + ModeNotice;
    const TCHAR* Turn = SignalDirection < 0 ? TEXT("left") : (SignalDirection > 0 ? TEXT("right") : TEXT("off"));
    if (Mode != EDriveMode::AT)
    {
        const TCHAR* Reasons[] = {TEXT(""), TEXT("one button only"), TEXT("depress LT"), TEXT("stop before reverse"), TEXT("over-rev"), TEXT("gear limit")};
        const FString Gear = Manual.Gear < 0 ? TEXT("R") : Manual.Gear == 0 ? TEXT("N") : FString::FromInt(Manual.Gear);
        return FString::Printf(TEXT("%s   %s   %s   %.0f rpm   %.1f km/h   Park %s   Doors %.0f/%.0f%%\nLT %.2f   engagement %.2f   slip %+.0f rpm   axle %+.0f Nm   %s %s %s"),
            ModeLabel(), *Gear, EngineLabel(), Manual.Rpm, GetForwardSpeedKmh(),
            bParking ? TEXT("ON") : TEXT("OFF"), 100.f*FrontDoor, 100.f*MiddleDoor, DriverClutch,
            Manual.Engagement, Manual.SlipRPM, Manual.AxleNm, Reasons[static_cast<int>(Manual.LastShift)],
            (Manual.Fault || bWheelFault) ? TEXT("INPUT/WHEEL FAULT") : TEXT(""), *Notice);
    }
    return FString::Printf(TEXT("AT (1086)   %s  gear %d   %.0f km/h   %.0f rpm   Park %s   Doors %.0f/%.0f%%   Lights %s   Turn %s   %s"),
        RangeName, M->GetCurrentGear(), FMath::Abs(GetForwardSpeedKmh()), M->GetEngineRotationSpeed(),
        bParking ? TEXT("ON") : TEXT("OFF"), 100.f * FrontDoor, 100.f * MiddleDoor,
        bLamps ? TEXT("ON") : TEXT("OFF"), Turn, *Notice);
}

const TCHAR* AKotoden1086Pawn::ModeLabel() const
{
    if (Mode == EDriveMode::AT) return TEXT("AT (1086)");
    return Mode == EDriveMode::Manual ? TEXT("Manual MT (fictional)") : TEXT("Auto-clutch MT (fictional)");
}

float AKotoden1086Pawn::EngineRPM() const
{
    const auto* M = CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
    return Mode == EDriveMode::AT ? M->GetEngineRotationSpeed() : Manual.Rpm;
}

int32 AKotoden1086Pawn::DisplayGear() const
{
    return Mode == EDriveMode::AT ? GetVehicleMovementComponent()->GetCurrentGear() : Manual.Gear;
}

void AKotoden1086Pawn::CycleMode()
{
    if (!bParking || !FMath::IsFinite(GetForwardSpeedKmh()) || FMath::Abs(GetForwardSpeedKmh()) > StationaryKmh)
    {
        ModeNotice = TEXT("T: stop and apply Park");
        return;
    }
    auto* M = CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
    if (M->GetNumWheels() != 4 || M->Wheels.Num() != 4) { ModeNotice = TEXT("waiting for four wheels"); return; }
    ModeNotice.Empty();
    // Keep the proven chassis alive. Native drivetrain is neutral and receives zero throttle
    // throughout MT. Override replaces BOTH torques on every wheel at the final Chaos stage.
    M->SetThrottleInput(0.f);
    M->SetUseAutomaticGears(false);
    M->SetTargetGear(0, true);
    Range = EBusDriveRange::Neutral;
    const auto Next = Mode == EDriveMode::AT ? EDriveMode::Manual :
        Mode == EDriveMode::Manual ? EDriveMode::AutoClutch : EDriveMode::AT;
    if (Next == EDriveMode::AT) ReleaseOverride();
    Mode = Next;
    Manual.Reset();
    if (const auto* Driver = Cast<ABusInputPlayerController>(GetController()))
    {
        const auto Input = Driver->GetDriverInputState();
        Manual.SynchronizeButtons(Input.bGearUpHeld, Input.bGearDownHeld);
        if (Mode != EDriveMode::AT) ApplyManual(Input, 0, true);
    }
}

void AKotoden1086Pawn::Ignition()
{
    if (Mode == EDriveMode::AT) return;
    if (!bParking || FMath::Abs(GetForwardSpeedKmh()) > StationaryKmh || Manual.Gear != 0)
    {
        ModeNotice = TEXT("I: stop, Park and select N");
        return;
    }
    ModeNotice.Empty();
    Manual.Ignition();
}

void AKotoden1086Pawn::ApplyManual(const FBusDriverInputState& Input, float Dt, bool bInterlock)
{
    auto& M = *CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
    BusMT::Input In;
    In.Throttle = Input.Throttle;
    In.Pedal = Input.Clutch;
    In.SpeedMS = GetForwardSpeedKmh() / 3.6f;
    In.Interlock = bInterlock;
    In.AutomaticClutch = Mode == EDriveMode::AutoClutch;
    In.Up = Input.bGearUpHeld;
    In.Down = Input.bGearDownHeld;
    bWheelFault = M.Wheels.Num() != 4 || M.GetNumWheels() != 4 || !FMath::IsFinite(AppliedBrake);
    for (int32 I = 0; I < M.GetNumWheels(); ++I)
    {
        if (!M.Wheels.IsValidIndex(I) || !M.Wheels[I] || !M.GetWheelState(I).bIsValid)
        { bWheelFault = true; continue; }
        const auto& State = M.GetWheelState(I);
        if (!FMath::IsFinite(State.DriveTorque) || !FMath::IsFinite(State.BrakeTorque)) bWheelFault = true;
        if (I == 2 || I == 3) In.AxleRadS += .5f * M.Wheels[I]->GetWheelAngularVelocity();
    }
    In.Interlock |= bWheelFault;
    Manual.Advance(Dt, In);
    for (int32 I = 0; I < M.GetNumWheels(); ++I)
    {
        const auto* Wheel = M.Wheels.IsValidIndex(I) ? M.Wheels[I].Get() : nullptr;
        float Brake = Wheel && FMath::IsFinite(AppliedBrake) ? AppliedBrake * Wheel->MaxBrakeTorque : 0.f;
        if (Wheel && bParking && I >= 2) Brake = FMath::Max(Brake, Wheel->MaxHandBrakeTorque);
        Brake = FMath::IsFinite(Brake) ? FMath::Max(Brake, 0.f) : 0.f;
        if (I < 4) BrakeNm[I] = Brake;
        M.SetDriveTorque(I >= 2 && !bWheelFault ? Manual.AxleNm*.5f : 0.f, I);
        M.SetBrakeTorque(Brake, I);
        M.SetTorqueCombineMethod(ETorqueCombineMethod::Override, I);
    }
}

void AKotoden1086Pawn::ReleaseOverride()
{
    if (Mode == EDriveMode::AT) return;
    auto& M = *CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
    for (int32 I = 0; I < M.GetNumWheels(); ++I)
    {
        M.SetDriveTorque(0, I);
        M.SetBrakeTorque(0, I);
        M.SetTorqueCombineMethod(ETorqueCombineMethod::None, I);
    }
    bWheelFault = false;
}

void AKotoden1086Pawn::EndPlay(const EEndPlayReason::Type Reason)
{
    ReleaseOverride();
    Super::EndPlay(Reason);
}

const TCHAR* AKotoden1086Pawn::EngineLabel() const
{
    if (Mode == EDriveMode::AT) return TEXT("Chaos AT");
    const TCHAR* States[] = {TEXT("Off"), TEXT("Starting"), TEXT("Running"), TEXT("Stalled")};
    return States[static_cast<int>(Manual.State)];
}

void AKotoden1086Pawn::ToggleRecording()
{
    Recorder->Toggle();
}

void AKotoden1086Pawn::RecordDrive(float Dt)
{
    FBusDriveReading R{};
    R.Mode = ModeLabel();
    R.Engine = EngineLabel();
    R.Rpm = EngineRPM();
    R.Gear = DisplayGear();
    R.SpeedMS = GetForwardSpeedKmh() / 3.6f;
    R.Clutch = DriverClutch;
    R.Engagement = Manual.Engagement;
    R.SlipRPM = Manual.SlipRPM;
    R.Throttle = DriverThrottle;
    R.Brake = AppliedBrake;
    R.Steer = DriverSteer;
    R.bPark = bParking;
    R.FrontDoor = FrontDoor;
    R.MiddleDoor = MiddleDoor;
    R.bManual = Mode != EDriveMode::AT;
    R.bFault = R.bManual && (Manual.Fault || bWheelFault);
    const auto& M = *CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
    for (int32 I = 0; I < 4; ++I)
    {
        auto& W = R.Wheels[I];
        W.DriveCmd = I >= 2 && !bWheelFault ? Manual.AxleNm * .5f : 0.f;
        W.BrakeCmd = BrakeNm[I];
        if (I >= M.GetNumWheels()) continue;
        const auto& Status = M.GetWheelState(I);
        W.bValid = Status.bIsValid;
        W.Drive = Status.DriveTorque;
        W.Brake = Status.BrakeTorque;
    }
    Recorder->Sample(Dt,R);
}
