#include "BusTripRecorder.h"
#include "HAL/FileManager.h"
#include "Misc/DateTime.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"

void UBusTripRecorder::Toggle()
{
    if (Writer) { Close(); return; }
    const FString Dir = FPaths::ProjectSavedDir() / TEXT("BusTelemetry");
    IFileManager::Get().MakeDirectory(*Dir, true);
    const FString Name = FDateTime::UtcNow().ToString(TEXT("%Y%m%d-%H%M%S")) + TEXT("-") + FGuid::NewGuid().ToString() + TEXT(".csv");
    Writer.Reset(IFileManager::Get().CreateFileWriter(*(Dir / Name), FILEWRITE_NoReplaceExisting));
    if (!Writer) { UE_LOG(LogTemp, Error, TEXT("Cannot start 1086 telemetry in %s"), *Dir); return; }
    NextSample = Elapsed = 0;
    bFaultSinceSample = false;
    Buffer = TEXT("time_s,frame_ms,mode,engine,rpm,gear,speed_m_s,lt,engagement,slip_rpm,rt,brake,steer,park,front_door,middle_door,lights,turn,cab,yaw_deg,fault");
    for (const auto* Wheel : {TEXT("fl"),TEXT("fr"),TEXT("rl"),TEXT("rr")})
        Buffer += FString::Printf(TEXT(",%s_drive_cmd_nm,%s_brake_cmd_nm,%s_drive_nm,%s_brake_nm"),Wheel,Wheel,Wheel,Wheel);
    Buffer += TEXT("\n");
    Flush();
}

void UBusTripRecorder::Flush()
{
    if (!Writer || Buffer.IsEmpty()) return;
    FTCHARToUTF8 Bytes(*Buffer);
    Writer->Serialize((void*)Bytes.Get(), Bytes.Length());
    Writer->Flush();
    Buffer.Reset();
    if (Writer->IsError())
    {
        UE_LOG(LogTemp, Error, TEXT("1086 telemetry write failed"));
        Writer.Reset();
    }
}

void UBusTripRecorder::Sample(float Dt, const FBusDriveReading& R)
{
    if (!Writer) return;
    bFaultSinceSample |= R.bFault || !FMath::IsFinite(Dt);
    Elapsed += FMath::IsFinite(Dt) ? FMath::Max(0.f, Dt) : 0.f;
    if (Elapsed + 1.e-7 < NextSample) return;
    // Store actual observations only. Do not duplicate physics samples after a slow frame.
    NextSample = (FMath::FloorToDouble((Elapsed + 1.e-7) * 20.) + 1.) / 20.;
    bool Fault = bFaultSinceSample;
    auto Number = [&Fault](double V) -> FString
    {
        if (!FMath::IsFinite(V)) { Fault = true; return FString(); }
        return FString::Printf(TEXT("%.5f"),V);
    };
    const FString Frame = Number(Dt * 1000.);
    FString Row = FString::Printf(TEXT("%.5f,%s,%s,%s,%s,%d"),Elapsed,*Frame,*R.Mode,*R.Engine,*Number(R.Rpm),R.Gear);
    for (float V : {R.SpeedMS,R.Clutch}) Row += TEXT(",") + Number(V);
    Row += TEXT(",") + (R.bManual ? Number(R.Engagement) : FString());
    Row += TEXT(",") + (R.bManual ? Number(R.SlipRPM) : FString());
    for (float V : {R.Throttle,R.Brake,R.Steer}) Row += TEXT(",") + Number(V);
    Row += R.bPark ? TEXT(",1") : TEXT(",0");
    Row += TEXT(",") + Number(R.FrontDoor) + TEXT(",") + Number(R.MiddleDoor);
    Row += FString::Printf(TEXT(",%d,%d,%d,%s"),int32(R.bHeadlights),R.Turn,int32(R.bCab),*Number(R.YawDeg));
    FString Axles;
    for (const auto& W : R.Wheels)
    {
        Axles += TEXT(",") + (R.bManual ? Number(W.DriveCmd) : FString());
        Axles += TEXT(",") + (R.bManual ? Number(W.BrakeCmd) : FString());
        Axles += TEXT(",") + (W.bValid ? Number(W.Drive) : FString());
        Axles += TEXT(",") + (W.bValid ? Number(W.Brake) : FString());
    }
    Buffer += Row + (Fault ? TEXT(",1") : TEXT(",0")) + Axles + TEXT("\n");
    bFaultSinceSample = false;
    if (Buffer.Len() >= 8192) Flush();
}

void UBusTripRecorder::Close()
{
    Flush();
    Writer.Reset();
}
void UBusTripRecorder::EndPlay(const EEndPlayReason::Type Reason)
{
    Close();
    Super::EndPlay(Reason);
}
