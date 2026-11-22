using UnrealBuildTool;

public class KotodenBusSimulatorEditorTarget : TargetRules
{
    public KotodenBusSimulatorEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_5;
        ExtraModuleNames.Add("KotodenBusSimulator");
    }
}
