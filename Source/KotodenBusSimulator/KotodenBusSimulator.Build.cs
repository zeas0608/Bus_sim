using UnrealBuildTool;

public class KotodenBusSimulator : ModuleRules
{
    public KotodenBusSimulator(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "ChaosVehicles" });
        PrivateDependencyModuleNames.AddRange(new[] { "EnhancedInput", "InputCore" });
    }
}
