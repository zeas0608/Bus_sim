# P0-4 独自クラッチと Chaos Vehicles の接続調査

P0-1〜P0-3 はユーザーの Windows（UE 5.5.4）で検証済み。今回、比較用に読めたエンジンのソースは **5.3.2**。Epic の 5.5.4 ソースにはこのクラウド環境からアクセスできず、UE も入っていない。以下の接続方法は **5.5.4 での確認候補**。走行コードの変更は保留し、手元の UE で根拠を確認するためのスクリプトを追加した。

## 読み取れた構造と 5.5.4 で確認する箇所

P0-3 の `ABusPrototypeVehiclePawn` は `AWheeledVehiclePawn` を継承する。RT・左スティック X・A を標準のスロットル・操舵・ブレーキに渡し、A の押し時間から連続ブレーキ指令を作る。LT は `GetDriverInputState()` から取得でき、踏み切りが 1、離した状態が 0。

以下は比較用の 5.3.2 ソースで確認した内容。プラグインファイルの起点は `Engine/Plugins/Experimental/ChaosVehiclesPlugin/Source/ChaosVehicles/`。

| ファイルとシンボル | 読み取れた処理 |
| --- | --- |
| `Public/ChaosWheeledVehicleMovementComponent.h` と `Private/ChaosWheeledVehicleMovementComponent.cpp` の `UChaosWheeledVehicleSimulation::ProcessMechanicalSimulation` | 標準系は車輪回転からエンジン回転を求め、エンジンの出力を変速機に渡す。差動装置の設定に基づく配分で、駆動輪ごとのトルクになる。この経路に LT で操作する摩擦クラッチの入力は見当たらなかった。 |
| 同上の `bMechanicalSimEnabled`、`UChaosWheeledVehicleSimulation::ApplyInput` | 生成前に機械系を無効にすると、標準エンジン・変速機・差動装置を生成しない。操舵、サスペンション、タイヤ接地の処理は別に進む。標準のエンジンブレーキはエンジンと変速機の存在に依存する。 |
| 同上の `UChaosWheeledVehicleMovementComponent::SetDriveTorque`、`SetBrakeTorque`、`SetTorqueCombineMethod`、`GetWheelState` | 車輪インデックスごとに外部トルクと合成方式を指定できる。入力のトルクは N·m で、エンジン内部で変換する。車輪計測値は `GetWheelState` の `FWheelStatus::DriveTorque` から取得する候補。 |
| `Public/ChaosVehicleWheel.h` の `ETorqueCombineMethod` と `ExternalTorqueCombineMethod`、`Engine/Source/Runtime/Experimental/ChaosVehicles/ChaosVehiclesCore/Private/WheelSystem.cpp` の `FSimpleWheelSim::Simulate` | `Override` は駆動・制動の両トルクを外部値に置き換える。`Additive` は両トルクに外部値を加算し、外部値自体をクリアする。標準機械系を止めると、加算先の駆動トルクが毎ステップ再設定される保証をこの版のコードから得られない。 |

根拠: 比較用 [5.3.2 のバージョン情報](https://github.com/chenyong2github/UnrealEngine/blob/c865e168d0935b8e5f4bd865ddcc1c733c8ce7cf/Engine/Build/Build.version)・[車両プラグイン](https://github.com/chenyong2github/UnrealEngine/tree/c865e168d0935b8e5f4bd865ddcc1c733c8ce7cf/Engine/Plugins/Experimental/ChaosVehiclesPlugin/Source/ChaosVehicles)・[車輪シミュレーション](https://github.com/chenyong2github/UnrealEngine/blob/c865e168d0935b8e5f4bd865ddcc1c733c8ce7cf/Engine/Source/Runtime/Experimental/ChaosVehicles/ChaosVehiclesCore/Private/WheelSystem.cpp)。

## 接続候補と比較

| 方式 | 判断 |
| --- | --- |
| 通常の Chaos Vehicles に各輪の外部トルクを入力 | 最初に検証する候補。P0-3 の車体・車輪・入力・操舵を再利用できる。標準機械系を車両生成前に無効化し、`Override` を指定する車輪には駆動と制動の両方を送る。A は P0-3 の連続指令を使い、各輪のブレーキ設定から制動トルクを求める。上書きが制動や ABS に与える影響は実走で判定する。 |
| 通常の Chaos Vehicles のシミュレーションを拡張 | 公開 API で制動や物理ステップとの同期を維持できなければ比較する。車輪に渡す直前に駆動だけを差し替えられる可能性がある。5.5.4 での公開範囲や必要な派生クラスを確認し、拡張が成立するまではエンジン改変を前提にしない。 |
| Chaos Modular Vehicles | エンジン・クラッチ・変速機をモジュールとして扱える比較候補。通常の Wheeled Vehicle の Pawn、アセット構成、設定をそのまま移せるとは確認できていない。5.5.4 でのツールと実行環境、独自計算との接続点を別途検証する必要がある。 |

Modular の構成は [Epic の Chaos Modular Vehicles Quickstart](https://dev.epicgames.com/documentation/en-us/unreal-engine/chaos-modular-vehicles-quickstart?application_version=5.5) を参照。

候補の最小モデルは `車輪指令[N·m] = RT × 仮の最大エンジントルク[N·m] × (1 − LT) × 仮の固定総減速比 × 車輪への配分率`。最初は全駆動輪で配分率の合計を 1 にする。車輪側へ渡した後に標準変速機で再度ギア比を掛けない。LT=1 では駆動輪すべてにゼロを送る。線形の係合率は仮のモデルで、摩擦やスリップを表す物理量ではない。ギア比・最大トルク・RPM の実車値は今回追加していない。

## Windows の UE 5.5.4 で根拠を確認する

1. GitHub Desktop で **Fetch origin → Current Branch** から `p0/chaos-external-clutch` を選ぶ。P0-3 の走行レベルと Blueprint は手元のプロジェクトに置いたままでよい。
2. エクスプローラーでリポジトリを開き、アドレスバーに `powershell` と入力する。次のコマンドを実行する。`-UnrealRoot` は Launcher の **Unreal Engine → ライブラリ** で確認した実際の UE インストール先に置き換える。

   ```powershell
   .\scripts\Inspect-ChaosClutchApi.ps1 -UnrealRoot 'C:\Program Files\Epic Games\UE_5.5'
   ```

3. `Engine version: 5.5.4` を確認する。出力のファイル名と行番号を開き、次の点を確認する。シンボルが見つかっても、実装の動作保証にはならない。`FILE NOT FOUND` が出たら Launcher のインストールオプションの **Engine Source** を確認し、ソースがなければ Epic の認証済み GitHub で 5.5.4 のソースを確認する。
   - 駆動・制動 API がゲームモジュールから呼べる宣言か。外部トルクの単位と車輪インデックス、置換が効く段階を確認する。
   - 機械系を車両生成前に無効化すると、駆動とエンジンブレーキの標準経路が両方なくなるか。操舵・車輪接地は引き続き計算されるか。
   - `Override` の作用範囲、車輪トルクの読み戻し、書き込みが反映される物理ステップを確認する。実装が読めない場合はこの段階を未確認とする。
4. 既存車両の回帰確認は、UE を閉じて Visual Studio 2022 の **Development Editor / Win64** でビルドし、手元の P0-3 の走行レベルで **Play**。RT で発進、左スティックで旋回、A で停止する。このブランチにクラッチ走行モードはないため、P0-4 の走行確認とは区別する。

## 次の判断

**本格 MT の実装は保留。** 5.5.4 の確認後、P0-3 の既定車両に影響しない、スポーン時に選べる試作モードを先に検証する。RT 一定で LT を離す・半押し・踏み切りの順に試し、HUD の係合率と指令に加え、Chaos が返す各輪の駆動トルクを記録する。停止状態から LT を踏み切って RT を押しても駆動が発生しないこと、走行中に LT を踏み切っても惰性は残り得ること、A と操舵が使えること、停止・再スポーン・異なるフレームレートで外部トルクが残らないことを確認する。その結果が揃ってから、エンジン慣性・クラッチ滑り・独自 MT の設計に進む。エンスト、始動、温度、故障、正式車両は今回扱わない。

このクラウド環境での P0-4 は **ビルド未実施 / UE実行未確認 / F310実機未検証**。
