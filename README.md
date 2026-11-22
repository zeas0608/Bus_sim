# Kotoden Bus Simulator（個人開発）

日本の路線バスの運転と業務を再現する、Windows向け3Dバスシミュレーターのプロジェクト。

**最終目標:** ことでんバスをモデルに、高松駅発の御厩線を実在道路に近い高松市の3Dマップ上で運転する。

**最初の目標:** Unreal Engine 5で、仮バスとテストコースを使い、Logicool F310で完全MT・クラッチ自動MTを運転できる状態を作る。

## 開発環境

- Unreal Engine 5（まずUE 5.5.4を試す。正式確定は実機検証後）
- Windows PC（Core i5-12400、RTX 3060、RAM 16 GB）
- C++ / Blueprint / Visual Studio 2022 Community / Blender / Codex
- 1280×720、60fps目標（未計測）

## Windows でエディターを開く（P0）

1. Epic Games Launcher で Unreal Engine 5.5.4 をインストールし、パッチバージョンを確認する。`.uproject` の `EngineAssociation` は Launcher の登録名 `5.5` を指定するため、この値だけでは 5.5.4 に固定されない。
2. Visual Studio Installer で Visual Studio 2022 Community（17.8 以降、17.10 推奨）に「C++ によるゲーム開発」ワークロード、MSVC v143 x64/x86 ビルドツール、Windows 10/11 SDK を入れる。対応するツールチェーンは [Epic の Visual Studio セットアップ手順（UE 5.5）](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine?application_version=5.5) を参照。
3. このブランチをチェックアウトし、リポジトリ直下の `KotodenBusSimulator.uproject` を右クリックして「Generate Visual Studio project files」を選ぶ（Windows 11 では「その他のオプションを表示」の中にある場合がある）。別のエンジンが選ばれている場合は「Switch Unreal Engine version」で、インストールした 5.5.4 を選ぶ。
4. 生成された `KotodenBusSimulator.sln` を Visual Studio で開き、`Development Editor` / `Win64` を選択して `KotodenBusSimulator` プロジェクトをビルドする。ビルドが成功したら `KotodenBusSimulator.uproject` をダブルクリックしてエディターを起動する。
5. エンジン付属の空マップ `Entry` が開くことと、「Edit → Plugins」で Chaos Vehicles と Enhanced Input が有効になっていることを確認する。必要に応じて「Play」で空マップの実行開始・停止を確認する。

使用するプラグインは UE 5.5.4 に同梱の Chaos Vehicles と Enhanced Input。P0-3 の走行確認には同梱の Vehicle テンプレートから車両アセットを取り込む。UE の利用条件が適用され、有料アセットは不要。

**P0-1 の検証状況:** ユーザーの Windows 環境（UE 5.5.4、Visual Studio 2022）で C++ ビルドとエディター起動に成功。

## P0-2: F310の入力を画面に表示する

作業ブランチは `p0/f310-input-diagnostics`。

1. UE5 を終了してから Visual Studio 2022 で `Development Editor` / `Win64` を選び、ビルドする。
2. `KotodenBusSimulator.uproject` を開き、`Entry` マップで **Play** を押す。
3. プレイ画面をクリックし、XInputモードのF310を動かす。
4. Cyan（シアン色）のデバッグ表示でRT/LT、左・右スティック、A/LB/RBを確認する。

既定の構成では Blueprint アセットの設定は不要。GameMode が入力用 Controller と診断用 HUD を選び、Controller が Enhanced Input アクションとマッピングを生成する。
**P0-2 はユーザーの Windows 実機で F310 の全入力を確認済み**。詳細は [F310入力テスト手順](docs/P0-2-F310-TEST.md) を参照。

## P0-3: Chaos 仮車両の走行

UE 5.5.4 の Vehicle テンプレートから仮車両のアセットを移行し、車両 Blueprint と平坦な走行レベルを作る。C++ 側は P0-2 の入力を再利用し、RT・左スティック X・A を Chaos に渡す。追従カメラと、車速・連続ブレーキ指令の表示を追加した。

最初に [Windows でのアセット設定と走行確認](docs/P0-3-CHAOS-DRIVE.md) を参照。P0-3 はユーザーの Windows（UE 5.5.4）で F310 による発進・旋回・停止を確認済み。

## P0-4: 独自クラッチと Chaos の接続調査

車輪への外部トルク入力と標準駆動系の調査結果は [技術メモ](docs/P0-4-CHAOS-CLUTCH.md) を参照。ユーザーの UE 5.5.4 で API と `Override` の挙動をソース確認済み。

P0-4B では試作用 `BusClutchPrototypeVehiclePawn` を追加した。通常の P0-3 車両と切り替える方法、仮値、確認項目は [独自クラッチ走行試作の手順](docs/P0-4B-CLUTCH-DRIVE.md) を参照。P0-4B は **ビルド未実施 / UE実行未確認 / F310実機未検証**。

## C++ と Blueprint の構成

`Source/KotodenBusSimulator/` はゲーム用の Runtime モジュール。実装は `Private/` に置き、新しい型を他モジュールに公開する必要ができた時点で `Public/` を使う。UE API の入口は Chaos Vehicles の `UChaosWheeledVehicleMovementComponent` と、Enhanced Input の `UEnhancedPlayerInput` / `UEnhancedInputComponent` を想定する。P0-2 の入力状態は `GetDriverInputState()` で C++ と Blueprint から参照できる。診断用 HUD はこの値を読み取って表示する。

| 今後の配置 | 担当する処理 |
| --- | --- |
| `Private/Input/` | Enhanced Input の入力を受け、正規化した操作指令に変換する。視点と H パターンの切り替えもここで管理する。 |
| `Private/Vehicle/` | 車体・車輪と Chaos の接続を扱う。動力系（エンジン、クラッチ、MT）と常用・駐車ブレーキの計算は別の責務として分ける。車輪へのトルクの接続方法は P0 の後続検証で判断する。 |
| `Private/Camera/` | 視点の切り替えとカメラ操作を扱う。 |
| `Private/Telemetry/`、`Content/UI/` | C++ で車両状態を取得し、将来のログ記録と Blueprint HUD に読み取り用の状態を渡す。 |

必要なディレクトリは機能追加時に作る。調整値は今後 Data Asset や Curve で管理し、シーン・演出・UI は Blueprint で構成できるようにする。

## ドキュメント

- [開発仕様書](docs/SPECIFICATION.md)
- [ロードマップ](docs/ROADMAP.md)
- [Codex向けルール](AGENTS.md)

## Codexで最初にやること

`docs/ROADMAP.md` の **P0: 技術スパイク** だけに着手する。UEプロジェクト作成・F310入力表示・Chaos Vehiclesを土台とした独自MTクラッチの接続可能性を確認し、未検証事項を報告する。

最初から実車モデルや高松市マップを作らない。

## ライセンスと公開について

個人利用用の開発リポジトリ。写真・ロゴ・音声・3D素材・地図にはそれぞれの権利がある。外部データを利用する際は利用条件と出典を確認する。ユーザーの同意なく有料サービスを使わない。
