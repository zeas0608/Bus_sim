#include "Kotoden1086ImportLibrary.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/SkeletalMesh.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/BoxElem.h"
#include "ReferenceSkeleton.h"
#if __has_include("PhysicsEngine/SkeletalBodySetup.h")
#include "PhysicsEngine/SkeletalBodySetup.h"
#endif
#include "UObject/Package.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, KotodenBusSimulatorEditor)

UPhysicsAsset* UKotoden1086ImportLibrary::CreateChassis(USkeletalMesh* Mesh, const TMap<FName, FVector>& ExpectedBonesCm)
{
    if (!Mesh || !Mesh->GetOutermost()->GetName().StartsWith(TEXT("/Game/Kotoden1086/"))
        || Mesh->GetPhysicsAsset() || ExpectedBonesCm.Num() == 0)
    {
        UE_LOG(LogTemp, Error, TEXT("1086 import: expected a new bus mesh without a physics asset."));
        return nullptr;
    }

    const FReferenceSkeleton& Skeleton = Mesh->GetRefSkeleton();
    if (Skeleton.FindBoneIndex(TEXT("root")) != 0)
    {
        UE_LOG(LogTemp, Error, TEXT("1086 import: expected a single chassis root named root."));
        return nullptr;
    }

    const TArray<FTransform>& RestPose = Skeleton.GetRefBonePose();
    for (const TPair<FName, FVector>& Entry : ExpectedBonesCm)
    {
        int32 Index = Skeleton.FindBoneIndex(Entry.Key);
        if (Index == INDEX_NONE)
        {
            UE_LOG(LogTemp, Error, TEXT("1086 import: missing bone %s."), *Entry.Key.ToString());
            return nullptr;
        }

        FTransform ComponentTransform = RestPose[Index];
        while ((Index = Skeleton.GetParentIndex(Index)) != INDEX_NONE)
        {
            ComponentTransform *= RestPose[Index];
        }
        if (!ComponentTransform.GetTranslation().Equals(Entry.Value, 1.0))
        {
            UE_LOG(LogTemp, Error, TEXT("1086 import: %s is at %s cm, expected %s cm; check FBX axis and scale."),
                *Entry.Key.ToString(), *ComponentTransform.GetTranslation().ToString(), *Entry.Value.ToString());
            return nullptr;
        }
    }

    const FString AssetName = TEXT("PA_Kotoden1086");
    const FString PackageName = FPackageName::GetLongPackagePath(Mesh->GetOutermost()->GetName()) / AssetName;
    if (FindPackage(nullptr, *PackageName) || FPackageName::DoesPackageExist(PackageName))
    {
        UE_LOG(LogTemp, Error, TEXT("1086 import: physics package already exists: %s"), *PackageName);
        return nullptr;
    }

    UPackage* Package = CreatePackage(*PackageName);
    UPhysicsAsset* Asset = NewObject<UPhysicsAsset>(Package, FName(*AssetName), RF_Public | RF_Standalone | RF_Transactional);
    USkeletalBodySetup* Chassis = NewObject<USkeletalBodySetup>(Asset, NAME_None, RF_Transactional);
    Chassis->BoneName = TEXT("root");

    // Provisional simple chassis envelope, centered clear of the tire contact patches.
    const FTransform ChassisBox(FVector(-11.5, 0.0, 135.0));
    const FTransform BoxInBoneSpace = ChassisBox.GetRelativeTransform(RestPose[0]);
    const FVector BoneSpaceSize = BoxInBoneSpace.GetScale3D().GetAbs() * FVector(835.0, 208.0, 185.0);
    FKBoxElem Box(BoneSpaceSize.X, BoneSpaceSize.Y, BoneSpaceSize.Z);
    Box.Center = BoxInBoneSpace.GetTranslation();
    Box.Rotation = BoxInBoneSpace.Rotator();
    Chassis->AggGeom.BoxElems.Add(Box);
    Asset->SkeletalBodySetups.Add(Chassis);
    Asset->UpdateBodySetupIndexMap();
    Asset->UpdateBoundsBodiesArray();
    Asset->SetPreviewMesh(Mesh);
    Mesh->SetPhysicsAsset(Asset);
    Mesh->MarkPackageDirty();
    FAssetRegistryModule::AssetCreated(Asset);
    Asset->MarkPackageDirty();
    return Asset;
}
