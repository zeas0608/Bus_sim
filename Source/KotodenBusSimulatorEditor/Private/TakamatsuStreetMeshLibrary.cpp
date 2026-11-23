#include "TakamatsuStreetMeshLibrary.h"

#include "AssetCompilingManager.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "CollisionQueryParams.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "Misc/PackageName.h"
#include "PhysicsEngine/BodySetup.h"
#include "StaticMeshAttributes.h"
#include "UObject/Package.h"

UStaticMesh* UTakamatsuStreetMeshLibrary::CreateStreetMesh(const FString& PackageName,
    const TArray<FVector>& Vertices, const TArray<int32>& Triangles, UMaterialInterface* Material, bool bGroundCollision)
{
    if (!PackageName.StartsWith(TEXT("/Game/TakamatsuRoute/Stage01/Build_"))
        || !FPackageName::IsValidLongPackageName(PackageName) || FPackageName::DoesPackageExist(PackageName)
        || FindPackage(nullptr, *PackageName) || !Material || Vertices.IsEmpty()
        || Triangles.IsEmpty() || Triangles.Num() % 3 != 0)
    {
        return nullptr;
    }

    FMeshDescription Description;
    FStaticMeshAttributes Attributes(Description);
    Attributes.Register();
    Attributes.GetVertexInstanceUVs().SetNumChannels(1);
    auto Positions = Attributes.GetVertexPositions();
    for (const FVector& Position : Vertices)
    {
        if (Position.ContainsNaN())
        {
            return nullptr;
        }
        Positions[Description.CreateVertex()] = FVector3f(Position);
    }
    const FName SurfaceSlot(TEXT("Surface"));
    const FPolygonGroupID Group = Description.CreatePolygonGroup();
    Attributes.GetPolygonGroupMaterialSlotNames()[Group] = SurfaceSlot;
    for (int32 Index = 0; Index < Triangles.Num(); Index += 3)
    {
        TArray<FVertexInstanceID, TInlineAllocator<3>> Corners;
        for (int32 Corner = 0; Corner < 3; ++Corner)
        {
            const int32 Point = Triangles[Index + Corner];
            if (!Vertices.IsValidIndex(Point))
            {
                return nullptr;
            }
            const FVertexInstanceID Instance = Description.CreateVertexInstance(FVertexID(Point));
            Attributes.GetVertexInstanceUVs().Set(Instance, 0, FVector2f(Vertices[Point].Y / 100, Vertices[Point].X / 100));
            Corners.Add(Instance);
        }
        Description.CreatePolygon(Group, Corners);
    }

    UPackage* Package = CreatePackage(*PackageName);
    const FName Name(*FPackageName::GetLongPackageAssetName(PackageName));
    UStaticMesh* Mesh = NewObject<UStaticMesh>(Package, Name, RF_Public | RF_Standalone | RF_Transactional);
    Mesh->GetStaticMaterials().Emplace(Material, SurfaceSlot, SurfaceSlot);
    FStaticMeshSourceModel& Model = Mesh->AddSourceModel();
    Model.BuildSettings.bRecomputeNormals = true;
    Model.BuildSettings.bRecomputeTangents = true;
    Model.BuildSettings.bGenerateLightmapUVs = false;
    Mesh->CreateMeshDescription(0, MoveTemp(Description));
    Mesh->CommitMeshDescription(0);
    Mesh->CreateBodySetup();
    UBodySetup* Body = Mesh->GetBodySetup();
    // Chaos wheel queries require a simple-channel hit on the triangulated street (including its holes).
    Body->CollisionTraceFlag = CTF_UseComplexAsSimple;
    Body->bDoubleSidedGeometry = bGroundCollision;
    Mesh->Build(false);
    FAssetRegistryModule::AssetCreated(Mesh);
    Mesh->MarkPackageDirty();
    return Mesh;
}

bool UTakamatsuStreetMeshLibrary::CheckDepartureGround(AActor* PlayerStart, UStaticMesh* Asphalt)
{
    if (!PlayerStart || !Asphalt || !PlayerStart->GetWorld())
    {
        return false;
    }
    // Reopening the level can start async compilation before the first physics query.
    FAssetCompilingManager::Get().FinishAllCompilation();
    FCollisionQueryParams QueryParams;
    QueryParams.AddIgnoredActor(PlayerStart);
    // The current 1086 rig has a 4.40 m wheelbase and 1.88 m track.
    for (const float X : {-220.0f, 220.0f})
    {
        for (const float Y : {-94.0f, 94.0f})
        {
            const FVector From = PlayerStart->GetActorTransform().TransformPosition(FVector(X, Y, 50));
            FHitResult Hit;
            if (!PlayerStart->GetWorld()->LineTraceSingleByChannel(Hit, From, From - FVector(0, 0, 400),
                ECC_Visibility, QueryParams))
            {
                return false;
            }
            const UStaticMeshComponent* Ground = Cast<UStaticMeshComponent>(Hit.GetComponent());
            if (!Ground || Ground->GetStaticMesh() != Asphalt)
            {
                return false;
            }
        }
    }
    return true;
}
