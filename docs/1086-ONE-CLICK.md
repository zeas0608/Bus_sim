# 1086号車：Windowsで最小操作の導入（自動化ツール）

このページは `vehicle/kotoden-1086` のモデル・コードを使って Windows UE 5.5.4 で最初の走行を試すための手順。

## ユーザーが行う操作

### 初回だけ：ブランチ切り替え前にバックアップ

UE5 / Visual Studio / Blender を閉じる。GitHub Desktopでブランチを切り替える**前**に、手元の `C:\UnrealProjects\Bus_sim\Content` と `Config` を、リポジトリの外側（例：`C:\UnrealProjects\Recovery_Backup\Before1086`）へコピーする。ローカルで作ったP0-3/P0-4Bの `.uasset`/`.umap` はGitHubにコミットされていないため、この手順が重要。

GitHub Desktopで Fetch origin → Current Branch → `tooling/one-click-1086` → 必要なら Pull origin。**Stash / Discard / force checkout** は行わない。ローカル変更の処理を求められたら先に確認する。

### 自動実行

`C:\UnrealProjects\Bus_sim\scripts\START_KOTODEN1086.cmd` をダブルクリックする。

スクリプトは次を順に実施：
1. UE5.5.4と必要ファイルを検査し、Editor起動中なら中断する。
2. `Content` と `Config` を `C:\UnrealProjects\Recovery_Backup\Kotoden1086-日時` に複製する（元ファイルは変更しない）。
3. VS2022向けプロジェクトファイル生成（コマンド実行）。
4. `KotodenBusSimulatorEditor Win64 Development` をコマンドでビルド。
5. ビルド成功時のみ、`UnrealEditor.exe` を `-ExecutePythonScript` 付きで起動。エディター内で `import_kotoden1086.py` が新しい `/Game/Kotoden1086/Build_###` にモデル、Blueprint、試走レベルを生成する。

**Visual StudioのUI操作と手動のPython実行は不要**。ただしUE5.5.4実機での自動実行は未検証なので、失敗した場合は以下のログを確認する。

## 成功したか確認する

エディターが起動したら、新規 `L_1086_Drive` が開いているか確認する。実行結果は `Saved\Setup1086\LatestImportResult.txt` に記録する。

- `SUCCESS`: インポートスクリプト自体が正常終了した（走行成功の意味ではない）。
- `FAILED`: ファイル内のPython例外を共有する。
- `RUNNING` のまま／ファイルなし：Editor起動・Python起動段階を確認する。
- ビルド失敗：`Saved\Setup1086\日時-BuildEditor.log` の最後のエラーを共有する。
- プロジェクトファイル生成失敗：`Saved\Setup1086\日時-GenerateProjectFiles.log` を共有する。

UE5のPlayを押して、1086号車の車体・車輪とHUDを確認する。初期状態は N/Park ON。停止状態で A を保持しながら 1 でD、Spaceで駐車ブレーキ解除、Aを離してRTで発進。左スティックで旋回、Aで停止、Cで車外視点。ほかの機能は [運転手順](1086-DRIVING.md)。

## 安全と限界

- このツールは `git checkout`、`stash`、`clean`、`reset` を実行せず、既存のアセットを削除しない。
- `import_kotoden1086.py` は毎回別の `Build_###` フォルダーに出力する。再実行すると新規アセットが増える。
- Epicの既存テンプレートアセットはGitHubへアップロードしない。
- WindowsでのC++ビルド、UEインポート、F310実走行は**まだ未検証**。エラーに応じてこの自動化またはインポートを修正する必要がある。
- Unreal Engineコマンド行からのPythonエディタ実行はEpic公式の `-ExecutePythonScript` 機能を使う。
