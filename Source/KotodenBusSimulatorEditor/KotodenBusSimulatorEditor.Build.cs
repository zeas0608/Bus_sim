using UnrealBuildTool;

public class KotodenBusSimulatorEditor : ModuleRules
{
    public KotodenBusSimulatorEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] { "AssetRegistry", "PhysicsCore" });
    }
}
