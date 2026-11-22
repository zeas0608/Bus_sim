# Kotoden Bus Simulator（個人開発）

日本の路線バスの運転と業務を再現する、Windows向け3Dバスシミュレーターのプロジェクト。

**最終目標:** ことでんバスをモデルに、高松駅発の御厩線を実在道路に近い高松市の3Dマップ上で運転する。

**最初の目標:** Unreal Engine 5で、仮バスとテストコースを使い、Logicool F310で完全MT・クラッチ自動MTを運転できる状態を作る。

## 開発環境

- Unreal Engine 5（まずUE 5.5.4を試す。正式確定は実機検証後）
- Windows PC（Core i5-12400、RTX 3060、RAM 16 GB）
- C++ / Blueprint / Visual Studio 2022 Community / Blender / Codex
- 1280×720、60fps目標（未計測）

## ドキュメント

- [開発仕様書](docs/SPECIFICATION.md)
- [ロードマップ](docs/ROADMAP.md)
- [Codex向けルール](AGENTS.md)

## Codexで最初にやること

`docs/ROADMAP.md` の **P0: 技術スパイク** だけに着手する。UEプロジェクト作成・F310入力表示・Chaos Vehiclesを土台とした独自MTクラッチの接続可能性を確認し、未検証事項を報告する。

最初から実車モデルや高松市マップを作らない。

## ライセンスと公開について

個人利用用の開発リポジトリ。写真・ロゴ・音声・3D素材・地図にはそれぞれの権利がある。外部データを利用する際は利用条件と出典を確認する。ユーザーの同意なく有料サービスを使わない。

※現段階はドキュメント整備中。UE5ゲーム本体は未実装。
