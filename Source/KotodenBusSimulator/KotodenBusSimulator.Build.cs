using UnrealBuildTool;

public class KotodenBusSimulator : ModuleRules
{
    public KotodenBusSimulator(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] { "ChaosVehicles", "EnhancedInput" });
    }
}
