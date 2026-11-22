# P0-2 F310 入力の実機確認

P0-1 はユーザーの Windows 環境でビルドとエディター起動を確認済み。P0-2 の変更は UE 5.5.4 でのビルド未実施 / UE実行未確認 / F310実機未検証。

## 1. ブランチを更新してビルドする

1. Unreal Editor を閉じる。GitHub Desktop で **Fetch origin** を押し、**Current Branch** から `p0/f310-input-diagnostics` を選ぶ。**Pull origin** が表示されたら押す。
2. リポジトリ直下の `KotodenBusSimulator.uproject` を右クリックし、**Generate Visual Studio project files** を実行する。生成された `KotodenBusSimulator.sln` を Visual Studio 2022 で開く。
3. `Development Editor` / `Win64` を選び、`KotodenBusSimulator` プロジェクトをビルドする。失敗したら、ビルド出力の先頭のエラーを記録する。

## 2. エディターで入力を確認する

1. F310 を USB に接続し、背面スイッチを **X**（XInput）にする。
2. `KotodenBusSimulator.uproject` を開き、`Entry` マップで **Play** を押す。プレイ画面をクリックしてフォーカスを合わせる。
3. シアン色の `P0-2 F310 / XInput` が出たら、次の操作を試す。

| 操作 | 期待する表示 |
| --- | --- |
| RT / LT を片方ずつ、次に両方押す | RT はアクセル、LT はクラッチ。両方が独立して 0〜1 で変化する。LT は 0 がペダルを離した状態、1 が踏み切った状態。 |
| 左スティックを左右へ倒す | `Left X steering` が -1〜1。縦だけの操作で大きく変化しない。 |
| 右スティックを左右・上下・斜めへ倒す | `Right X` と `Right Y` がそれぞれ -1〜1。斜めでは両方が変化する。 |
| A / LB / RB を順に押す | ブレーキ / ギアダウン / ギアアップが、それぞれ保持中は `ON`、離すと `OFF`。 |
| 全操作を離し、Play を終了してから再開する | アナログ値は中心や未押下で 0 に戻り、ボタンはすべて `OFF`。 |

スティックのデッドゾーンは軸ごとに 0.10、トリガーは 0.03 が初期値。範囲内は 0 とし、範囲外は最大入力が ±1 または 1 になるように線形に再スケールする。A / LB / RB の表示はボタンの保持状態。制動や変速の挙動を確認する工程は後続作業。

表示が出ない場合は **Project Settings → Maps & Modes** の既定 GameMode が `BusInputGameMode` で、**World Settings → GameMode Override** が未指定または同じ GameMode であることを確認する。入力が反応しない場合は **Output Log** の `F310:`、プレイ画面のフォーカス、背面スイッチを確認する。Windows で **Win + R → joy.cpl → プロパティ** を開くと、OS がコントローラー入力を受けているか確認できる。

## 3. Blueprint で調整する場合

既定の診断には Blueprint の作成は不要。デッドゾーンを調整する場合は次の操作で設定できる。

1. `BusInputPlayerController` の子 Blueprint を作り、**Class Defaults → Bus Input** で `Stick Dead Zone` と `Trigger Dead Zone` を調整する。
2. `BusInputGameMode` の子 Blueprint を作り、**Player Controller Class** に手順1の Blueprint を指定する。
3. **Project Settings → Maps & Modes** の **Default GameMode** に手順2の Blueprint を指定し、Play で再試験する。既定の診断 HUD は子 GameMode に継承される。

Blueprint から入力を使う場合は、ローカル Player Controller を `BusInputPlayerController` にキャストして `Get Driver Input State` を呼び出す。
