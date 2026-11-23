#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "Kotoden1086ImportLibrary.generated.h"

class UPhysicsAsset;
class USkeletalMesh;

UCLASS()
class KOTODENBUSSIMULATOREDITOR_API UKotoden1086ImportLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Refuse a mismatched FBX rig or an existing asset. All positions are in UE component space, cm. */
    UFUNCTION(BlueprintCallable, Category = "Kotoden|Import")
    static UPhysicsAsset* CreateChassis(USkeletalMesh* Mesh, const TMap<FName, FVector>& ExpectedBonesCm);
};
