#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "TakamatsuStreetMeshLibrary.generated.h"

class UMaterialInterface;
class UStaticMesh;

/** Editor-only construction of map layers in a fresh Stage01 package. Vertices are UE centimetres. */
UCLASS()
class KOTODENBUSSIMULATOREDITOR_API UTakamatsuStreetMeshLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Takamatsu|Import")
    static UStaticMesh* CreateStreetMesh(const FString& PackageName, const TArray<FVector>& Vertices,
        const TArray<int32>& Triangles, UMaterialInterface* Material, bool bGroundCollision);
};
