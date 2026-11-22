using UnrealBuildTool;

public class KotodenBusSimulatorTarget : TargetRules
{
    public KotodenBusSimulatorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_5;
        ExtraModuleNames.Add("KotodenBusSimulator");
    }
}
