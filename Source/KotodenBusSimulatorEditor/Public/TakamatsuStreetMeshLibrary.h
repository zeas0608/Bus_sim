#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "TakamatsuStreetMeshLibrary.generated.h"

class AActor;
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

    /** UVs are per triangle corner for printed signs and planting. An empty array uses metre-scale projection. */
    UFUNCTION(BlueprintCallable, Category = "Takamatsu|Import")
    static UStaticMesh* CreateTexturedStreetMesh(const FString& PackageName, const TArray<FVector>& Vertices,
        const TArray<int32>& Triangles, const TArray<FVector2D>& TriangleUVs, UMaterialInterface* Material,
        bool bGroundCollision);

    /** Verify that simple wheel queries hit the saved street at all four 1086 wheel positions. */
    UFUNCTION(BlueprintCallable, Category = "Takamatsu|Import")
    static bool CheckDepartureGround(AActor* PlayerStart, UStaticMesh* Asphalt);
};
