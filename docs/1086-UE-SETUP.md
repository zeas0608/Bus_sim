# Windows / UE 5.5.4 で高松210あ1086を走らせる

同梱の独自モデルから、車体・物理アセット・表示用マテリアル・車両 Blueprint・GameMode と試走レベルをエディター内で作る。元データは `Art/Bus1086/Bus1086.fbx` と同じフォルダーの `Bus1086.json`。Blender をインストールしていない PC でも使える。**Windows 用 UE 5.5.4 のビルド、インポート、エディター実行、F310 実走は未検証。**

## 初回ビルド

1. Unreal Editor を終了する。GitHub Desktop の **Fetch origin → Current Branch** で`vehicle/kotoden-1086` に切り替える。手元のマップや Blueprint を別の作業フォルダーに置いている場合は、新しいフォルダーにブランチをチェックアウトして試走できる。
2. エクスプローラーでプロジェクト直下の `KotodenBusSimulator.uproject` を右クリックし、**Generate Visual Studio project files** を選ぶ。Windows 11 では **その他のオプションを表示** の中にあることがある。
3. 生成した `KotodenBusSimulator.sln` を Visual Studio 2022 で開く。**Development Editor / Win64** を選び、ソリューション エクスプローラーで **KotodenBusSimulator → 右クリック → ビルド** を実行する。インポート処理は Editor 専用モジュールにあるため、Editor ターゲットが必要。
4. ビルド成功後、`KotodenBusSimulator.uproject` を UE **5.5.4** で開く。同梱の2つのスクリプト用プラグインはエディターターゲット用に指定してある。**Edit → Plugins** で **Python Editor Script Plugin**、**Editor Scripting Utilities**、**Chaos Vehicles**、**Enhanced Input** が有効なことを確認する。プラグインを追加したらエディターを再起動する。

## モデルと試走レベルを生成する

1. Play 中なら停止する。保存したい作業は **File → Save All** で保存する。スクリプトは、ユーザーの既存マップを閉じる前に未保存の変更がないか確認する。
2. **Tools → Execute Python Script…**（日本語 UI では「ツール → Python スクリプトを実行」）を選び、このリポジトリの `scripts/import_kotoden1086.py` を開く。
3. **Window → Output Log** の `1086 import: writing new assets to /Game/Kotoden1086/Build_001` を確認する。Content Browser では **Content → Kotoden1086 → Build_001** に相当する。再実行時は空いている次の番号を使う。
4. 最後に **L_1086_Drive** が開く。Content Drawer に車体の Skeletal Mesh、新しい Skeleton、`PA_Kotoden1086`、`MI_…`、`BP_Kotoden1086`、`BP_KotodenDriveMode` があることを確認する。シェーダーの準備が完了するまで待つ。
5. **BP_Kotoden1086** をダブルクリックして **Class Defaults → Bus Mesh Asset** で車体の Skeletal Mesh が保存されたことを確認する。次に **Components → Mesh** を選ぶ。1086 の車体が表示され、**Skeletal Mesh Asset** に今回生成した Skeletal Mesh、**Collision Presets** に **Vehicle** が指定されていることを確認する。車輪・部品は native Pawn の表示コンポーネントがポーズを更新するため、**Anim Class** の割り当ては不要。車輪クラスとボーン名は native Pawn が設定する。
6. **PA_Kotoden1086** をダブルクリックする。Skeleton Tree の `root` に車体を覆う直方体が一つあり、底面がタイヤの接地面から浮いていることを確認する。タイヤ接地は Chaos の車輪・サスペンションで計算する。骨盤・車輪・ドア等に自動生成されたラグドールは使わない。
7. テストレベルで **Window → World Settings → GameMode Override** がこの Build フォルダーの `BP_KotodenDriveMode` を指していることを確認する。プロジェクト全体の **Maps & Modes** は変更不要。

## F310 で試走する

1. F310 の背面を **X** にして USB 接続する。**Play** の横のメニューで **Selected Viewport** と **Default Player Start** を指定し、**Play** を押す。初期状態は **N・駐車ブレーキ作動・ドア閉**。
2. ビューポートにフォーカスを合わせ、停車中にキーボードの **1** で **D** を選び、**Space** で駐車ブレーキを解除。RT を少しずつ押して加速し、左スティック X で操舵する。**C** で外部視点に切り替え、前輪の操舵・回転と車体が揃うか確認する。
3. RT を離して A を押し、減速して停止する。駐車ブレーキを掛け、**F / M** で前扉／中扉、**L** で前照灯、**Q / E** で左右方向指示器を試す。走行中のドア操作や開扉中の発進はインターロックの確認項目。運転席のクリック操作とシフトの詳細は [運転手順](1086-DRIVING.md) を参照。
4. テスト後に **Esc**。他のレベルを開き直す場合は **Content Drawer** から以前のレベルをダブルクリックする。P0 車両も各自の既存レベルから再度比較できる。

## 動かないときに確認する場所

| 症状 | 確認する場所 |
| --- | --- |
| Python メニューがない／`EditorAssetLibrary` が見つからない | プラグイン有効化と再起動を確認する。 |
| `Kotoden1086ImportLibrary` または `Kotoden1086Pawn` が見つからない | エディターを閉じ、上の **Development Editor / Win64** ビルドをやり直す。Build Output の先頭の C++ エラーを記録する。 |
| `FBX material ... missing` または `missing bone` | 同じ生成回の FBX と JSON を使用する。出力ログで最初に不一致となった材質名／ボーン名を確認する。 |
| `expected ... cm` の位置不一致 | FBX 上の座標値は cm、前方は +X。スクリプトは Legacy FBX を使い、余分なシーン軸変換や回転を加えない。生成メッシュの見かけだけを回して走行させず、元ファイル、両側のホイール軸距と左右符号を確認する。 |
| スクリプトが途中で終了した | Output Log の最初の例外を保存する。同じ Build フォルダーは上書きしない。新規フォルダー内の未保存アセットを確認し、必要な作業を保存してから再実行する。 |
| カメラが床にある／標準 Pawn が出た | テストレベルの **World Settings → GameMode Override** と **Default Pawn Class**、Player Start の周囲の空間を確認する。 |
| スケルトンの車体は見えるが床を落ちる／進まない | **Mesh → Simulate Physics**、**Vehicle** コリジョン、Mesh の `PA_Kotoden1086`、床の **BlockAll**、D レンジ、駐車ブレーキ、ドア表示、F310 の入力を確認する。 |
| 半透明ガラスが不透明 | Mesh の Materials タブで、ガラススロットが新規フォルダーのガラス用 MI に割り当てられているかを確認する。透過色・発光などは各 MI の **BaseColor / Opacity / Glow** で確認できる。 |
