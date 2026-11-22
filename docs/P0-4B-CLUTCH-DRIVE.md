# P0-4B 独自クラッチの走行試作

P0-3 の通常車両と別の Pawn を選び、RT と LT で後輪の駆動トルクを変える。P0-4B は **ビルド未実施 / UE実行未確認 / F310実機未検証**。P0-3 の発進・旋回・停止はユーザーの Windows で確認済み。

## 実装と UE 5.5.4 の根拠

- ユーザーは UE 5.5.4 / CL 40574608 の `ChaosWheeledVehicleMovementComponent.h` 系で `bMechanicalSimEnabled`、`SetTorqueCombineMethod`、`SetDriveTorque`、`SetBrakeTorque`、`GetWheelState` を確認した。また、`WheelSystem.cpp` の `FSimpleWheelSim::Simulate` で、`Override` が駆動と制動の両方を置き換え、`Additive` は加算した外部値をクリアすることを確認した。
- 標準機械系を生成後に切り替える方法は採らない。試作用 Pawn のコンストラクタと `AActor::PreRegisterAllComponents` でフラグをオフにする。後者は、複製した Blueprint に保存されていた値を、ネイティブコンポーネントの登録・物理ステート作成前に設定するために使う。走行中はフラグを変更せず、オンなら外部指令を遮断する。呼び出し順と、標準機械系の生成を分ける `UChaosWheeledVehicleMovementComponent::SetupVehicle` の詳細は、手元の 5.5.4 のソースでも照合する。クラウドで確認した同箇所の実装は比較用 5.3.2。
- 試作は標準スロットルを送らず、4輪を `Override` にして毎回駆動・制動の両方を送る。前輪の駆動指令は常に 0。サスペンション・車輪接地・操舵は従来の Chaos に任せる。A は P0-3 の連続ブレーキ指令を使う。標準のブレーキ入力レートとエンジンブレーキは、この試作の外部制動経路には入らない。
- Pawn の `TG_PrePhysics` のゲーム Tick で1回更新する。`Override` の外部値は別の値で上書きするまで残るため、LT 踏み切り・RT 解放のフレームにも駆動ゼロを送り、A 解放後は制動ゼロを送る。所有解除・`EndPlay` では両方をゼロにする。個々の API 呼び出しが非同期の同一サブステップで反映される保証は未確認。停止中でも RT を意図して押し、LT がつながっていれば、発進用の指令が出る。
- HUD の `cmd` は今回の入力から計算した指令、`Chaos` は `GetWheelState` の最新有効な車輪出力。駆動・制動トルクと接地を示す。物理側出力のコピー後に更新されるため、指令と同じ Tick の値とは限らない。路面に伝わった力の実測値でもない。ホイール出力生成と `FillWheelOutputState`、`ParallelUpdate` の経路で、値の更新と単位を照合できる。

ソースを照合する場合は [調査メモ](P0-4-CHAOS-CLUTCH.md) の PowerShell スクリプトを UE 5.5.4 のインストール先に対して実行する。外部 API の実装で `TorqueMToCm`、出力側で逆の変換を探す。コードは API に N·m の値を渡し、独自に単位変換しない。車輪インデックスは 0 始まりで **Wheel Setups** の並び順。駆動比はコード側で1回だけ掛ける。

## 仮値

以下は試作の初期値。車両 Blueprint の **Class Defaults → Clutch Prototype** で変更できる。

| 項目 | 初期値と計算 |
| --- | --- |
| 仮エンジントルク | RT × 250 N·m |
| クラッチ係合率 | 1 − LT。LT=0 は 1、LT=1 は 0 |
| 固定総減速比 | 4.0（無次元） |
| 駆動トルク | 後輪に左右50%ずつ。各輪は仮エンジントルク × 係合率 × 4.0 ÷ 2。RT=1、LT=0 で各 500 N·m。前輪は 0 N·m |
| 制動トルク | 4輪とも連続ブレーキ指令 × 1,200 N·m／輪。元の上昇・下降率はそれぞれ 2.0／秒と 3.0／秒 |

## Windows でビルドして Blueprint を設定する

1. UE エディターを閉じ、GitHub Desktop の **Fetch origin → Current Branch** で `p0/chaos-clutch-drive` を取得する。既存の P0-3 アセットは手元に残す。空のチェックアウトの場合は先に [P0-3 のセットアップ](P0-3-CHAOS-DRIVE.md) を行う。
2. `KotodenBusSimulator.uproject` を右クリックして **Generate Visual Studio project files**。Visual Studio 2022 で `KotodenBusSimulator.sln` を開き、**Development Editor / Win64** でビルドする。ビルドに失敗したら、出力の先頭のエラーを控える。
3. UE 5.5.4 でプロジェクトを開く。Content Browser で走行確認済みの P0-3 車両 Blueprint を右クリックして **Duplicate**。複製（例 `BP_F310ClutchPrototype`）を開き、**File → Reparent Blueprint** で **BusClutchPrototypeVehiclePawn** を選ぶ。元の Blueprint は走行比較用に残す。
4. 複製の **Components → Vehicle Movement Component → Wheel Setups** を展開する。4件あり、車体・前後輪のクラスと Bone Name が元と一致することを確認する。後輪左右の要素番号を調べ、**Class Defaults → Clutch Prototype** の **Rear Left Wheel Index** と **Rear Right Wheel Index** に設定する。既定の 2、3 は一例。**Mechanical Sim Enabled** はオフ、サスペンションと車輪摩擦はオン。Mesh・Anim Class が元と一致することを確認し、**Compile → Save**。
5. P0-3 の GameMode Blueprint を **Duplicate**。複製の **Class Defaults** で **Default Pawn Class** に手順3の車両を選び、**Compile → Save**。P0-3 の走行レベルも Content Browser で複製して開き、**Window → World Settings → GameMode Override** に試作用 GameMode を選ぶ。Player Controller と HUD は P0-3 から引き継ぐ。

## Play で確認する

F310 の背面を **X** にし、試作レベルで **Play** を押して画面内をクリックする。`P0-4B Chaos / External Clutch` と `External commands: ON` を確認する。`BLOCKED` が続く場合は試作用 Pawn、4輪の生成、重複しない後輪番号、機械系の設定を確認する。

| 操作 | 確認する結果 |
| --- | --- |
| 停止中に LT を踏み切り、A を離したまま RT を押す | 仮エンジントルクは増える。係合率・全輪の駆動指令・更新後の Chaos 駆動値は 0。平坦路で発進しない |
| RT 一定で LT をゆっくり離す | 係合率と後輪の駆動指令が増え、前輪の駆動は 0 のまま。タイヤのグリップと負荷に応じて車が発進する |
| 走行中に A を離したまま LT を踏み切る | 後輪の駆動指令と Chaos の値が 0 に戻り、係合解除だけで急停止しない |
| RT を離して左スティックと A を操作する | 左右の操舵が効く。A で4輪の制動指令が増えて停止し、A 解放後に制動指令が 0 に戻る。各輪の `ground` も確認する |
| RT 解放・停止後の数フレーム、Play を止めて再開、可能ならフレームレートを変えて再試験 | 入力ゼロのまま再駆動しない。指令と Chaos 出力がゼロに落ちるまでのずれや、ブレーキ・接地の違いを記録する。30/60 fps で比べる場合はコンソールの `t.MaxFPS 30` / `t.MaxFPS 60` を使い、終了時は `t.MaxFPS 0` で戻す |
| 元の P0-3 レベルで Play | `P0-3 Chaos / F310` が出て、以前どおり発進・旋回・停止できる |

変速機操作、エンスト、始動、摩擦・滑りモデル、実車の再現は範囲外。P0-4B の判定には、指令の計算に加えて UE 上で報告されたトルクと挙動の確認が必要。
