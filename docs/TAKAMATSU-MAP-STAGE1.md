# 高松駅・御厩線マップ Stage 1 — データ確認と実装仕様

- 状態: 実データ変換、新規UEレベル生成、Windows一括導入を実装。旧資料と公道330 mでの変換はクラウドで検査済み。現行の⑤番の停止位置、UE5.5.4のビルド・レベル保存、AT/MT実走は未検証。
- 作成日: 2026-11-23
- Issue: https://github.com/zeas0608/Bus_sim/issues/10
- ベース: `feature/1086-mt-driving`
- 作業用ブランチ: `feature/takamatsu-map-stage1`

## 目的と最初の成果物

高松駅⑤番のりば付近から御厩線47番の実際の進行経路に沿い、1086号車で安全に発進・停車・右左折できる**最初の短区間**をUE5.5.4上で制作する。

- 最初に進行経路を**公式資料と現行道路データで確定**する。データで確定できない部分は、作業を続けるための仮レイアウトと分かるよう表示し、実在の正確なルートとしては扱わない。
- 既存の試走場や `Content/Kotoden1086/Build_###` を変更しない。新規マップとデータを `Content/TakamatsuRoute/Stage01` の下に作る。
- バス用の既存 `BP_Kotoden1086` を現地ローカル Content から自動検出・参照。GitHubにバス用の `.uasset/.umap` がない環境でも、通常のコード・データ検証が可能な構成にする。
- 路面、側道、縁石、歩道、交差点の半径、バス停停止位置、標識・信号位置を**後で座標/寸法調整できるデータ駆動**にし、資料がない箇所は推定と記録。
- 16GB RAM、RTX3060、720pの動作に配慮し、最初は小さな領域のみ。60fpsは目標であって検証前に達成済みと書かない。
- 既存 Content / Config / Source とユーザーの非Git管理アセットを削除・強制チェックアウト・上書きしない。

## 一次資料・候補データ

| 目的 | 一次資料／公開元 | 現時点で確認したこと／注意 |
| --- | --- | --- |
| 公式路線・停留所 | [ことでんバス 御厩線・由佐線](https://www.kotoden.co.jp/publichtm/bus/rosen/yusa_mimaya/index.html) | 御厩線は47番、下り高松駅⑤番、栗林公園・御厩・県立総合プール行。**駅前からの全交差点・最初の停留所名/道路への出方は未確定**、推測しない |
| 都市建築物モデル | [国土交通省 PLATEAU Open Data](https://www.mlit.go.jp/plateau/open-data/) / [G空間情報センター](https://front.geospatial.jp/plateau_portal_site/) | 高松市の公開モデルあり。ポータルの公開一覧では高松市:2022。**駅前を覆う配布範囲/LOD/ファイルは別途検証** |
| PLATEAU形式・許諾 | [PLATEAU FAQ](https://www.mlit.go.jp/plateau/faq/) | CityGML主体（地域によりFBX等）。基本的にCC BY4.0等のオープンライセンス。**使うデータセット固有の利用条件と帰属を確認** |
| 道路・停留所形状候補 | [OpenStreetMap](https://www.openstreetmap.org/copyright) | ODbL 1.0。データを使う場合は `© OpenStreetMap contributors` 等の表示と、加工・再配布の条件を確認。道路の幅やレーン数は欠測・誤りがある可能性あり |
| 道路縁・標高候補 | [国土地理院 基盤地図情報](https://service.gsi.go.jp/kiban/) / [利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html) | ダウンロード可。基盤地図情報の道路縁/数値標高モデルについて利用条件・データ範囲・測量法上の取扱いを個別確認 |
| 入力資料の出典管理 | 各公開元 | 取得日時、データバージョン、位置精度、ライセンス、元URL、加工手順、実車との照合状況を保存 |

注: これらのウェブ上で確認した事実は、Codexが開発時に再確認すること。路線の画像やPDFは**位置関係の参照**として利用し、商用地図/写真/航空画像を勝手にメッシュ化・取り込まない。

## 実装設計の要点

1. `WGS84`の参照座標・ローカル原点を決定し、緯度経度からUE座標(cm)への一貫した変換を実装する。地理座標の単純な度数をcmとして使わない。回転/軸向きと座標精度を単体テスト。
2. 地図ソースを法的に区別して扱う。OSMの線分は道路中心線の**推定**であり、実際の縁石/車線境界の真値と見なさない。
3. Road spline/メッシュ生成と適切な**衝突面**を別途検証する。路面下にめり込まないこと、1086号車の曲がり切れる幅を確保すること。
4. UE Editor Python/Blender等は新規 `Stage01` フォルダーにだけ保存する。既存の `Build_001` / `Build_002` などへ上書き保存しない。
5. インポート用の自動化は、`-ExecutePythonScript`がエディターを終了させる特性を考慮し、準備処理と通常のマップ起動を分ける。
6. 新しいスクリプトは、GitHub DesktopでPull後のcmdダブルクリックだけで安全に導入できるようにする。途中失敗時にはログと復旧手順を明示。
7. 従来の1086試走場のAT/MTと車両BPを維持、ユーザーのWindows UE5.5.4で試走確認を行う。GitHub上で確認できるだけでは実走合格と判定しない。

## 2026-11-24：実走フィードバックと走行補助の調整

ユーザーのWindows UE5.5.4で新マップが開き、**道路幅が狭いように感じ、曲がると道路と周囲の段差へ落ちる（復帰可能）**と報告。従来の地図生成では未タグ道路に幅の仮値を使い、道路外の地面を**車道比18 cm低く**、歩道を14 cm高く生成していた。

### 緊急修正（次回のWindows再生成・実走待ち）

- 道路外地面の回復落差を**18 cm → 2.5 cm**へ。道路外へ車輪が触れても深く落ちないようにする（本来の縁石高さや道路測量の再現ではない）。
- 現行のOSM道路幅・車線幅のタグと基本道路メッシュは保つ。駅前の推定された曲がり角付近に**最大1.75 m分の補助走行余裕**を加えた、別名 `TurningApron` の仮設走行面を生成し、元の車道と異なる色で見えるようにする。
- `survey.json`に `turning_apron_area_m2`、`estimated_turn_apron_junction_count`、`ground_recovery_drop_m`、`estimated_turn_apron_extra_m` を記録。**本物の道路幅だと誤表示しない**。
- 単体回帰テストを追加。道路の接続やメッシュの実際の衝突はWindowsのF310/UEで再確認が必要。
- 今回は手持ちのローカル `Content/TakamatsuRoute/Stage01/Build_*` を上書きしない。生成形状のハッシュとインポートスクリプトが更新されるので、次回 `scripts/INSTALL_TAKAMATSU_STAGE1.cmd` を実行すると**別のBuildフォルダー**に新マップが生成される。

この変更は**一時的な操作性改善**。正式版に向けて道路幅、内輪差、交差点内側の縁石線、停止位置を公式資料・現地写真・適切な公開データで照合し、補助走行面を徐々に廃止する。

### 外観・ストリートビュー・写真の扱い

現在の高松駅周辺モデルはOSMの地物輪郭・PLATEAUの取得可能な建築物輪郭/高さ・地理院標高から作る**簡易3Dジオメトリ**で、フラットな仮マテリアルを割り当てている。実際の壁色、窓、屋根、看板、駅前の上屋、路面標示の再現は後続の**同じ高松マップ工程**で行う。高松駅エリアのPLATEAU LOD2/テクスチャの対象範囲とライセンスは事前確認する。現状では**ゲームにLOD2テクスチャを取り込んだとは扱わない**。

Googleストリートビューは人が道路風景を比較・観察するための参考にできるが、Street View画像を機械的に収集/貼り付けたり、Google画像をトレースして地図/建物の3Dモデルを抽出する処理は追加しない。Google Maps Platformの[規約](https://cloud.google.com/archive/maps-platform/terms-20260623)と[Google Maps画像の使用ガイドライン](https://about.google/brand-resource-center/products-and-services/geo-guidelines/)を守る。代わりに、PLATEAU（配布データ固有の許諾確認）、[Mapillary CC BY-SA](https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data)、個人撮影、許諾のある自治体公開写真等を活用する。

最終的には高松駅の外観、バスのりば上屋・柱、建物の外壁色/窓、路面の舗装・車線・横断歩道・看板・信号灯器などを現実の見た目へ近づける。推定の色/形と裏付けのある実物を区別する。

### 追加の道路幅修正（同日・ユーザー再試走後）

段差と交差点は改善したが、**依然として道路が狭く感じる**との追加報告。コード上の既定値では、幅タグなしの `residential/service` は5.5m、2車線タグのみの場合は6.2m（3.1m×2）となる。これはOSMの現地実測幅ではなく、生成器の仮定。

- **OSMで明示的な`width`タグがある道路は変更しない。** 現地の正しさを確認する必要がある場合は`survey.json`の `features` を調べる。
- 幅タグなし、かつ47番の経路線に近く**並行する道路**だけに、別色の `WidthEstimate` を作る。交差するだけの側道は広げない。
- 訓練用の仮の走行可能幅：一方通行1車線は最低 **6.4m**、2車線相当以上は最低 **7.6m**（推定幅であり高松市の実測道路幅ではない）。元のアスファルト層を維持し、道路外の帯として分ける。地図外形、建築物/島との重なりを除外。
- `survey.json`に `estimated_width_segments` (元道路幅、仮幅、OSM地物ID)、`estimated_width_extra_area_m2`、`width_reproduction_note` を記録。
- `overview.svg`でも推定幅・旋回補助を薄い灰色で区別。**正確な幅/縁石位置を実測または公式データで裏取りするまで完成版とはしない**。
- 更新は現行試走マップを上書きせず、新しい `Build_*` フォルダーに生成する。Windows F310実走・メッシュ衝突は未検証。まだ狭ければ**該当場所のスクリーンショット**と`Saved/TakamatsuStage1/survey.json`を照合して部分修正する。

## Stage 1 合格チェック

- [ ] 公式路線と最初の短区間の道路接続、出典を確定
- [x] 取得・変換ツール、出典・ハッシュ・精度の記録を実装し、ローカル入力で再実行を検査
- [ ] 新規のバスターミナル・道路・交差点・衝突・信号/停止位置を生成
- [ ] 新規マップをUEに保存し、既存1086車両を配置
- [x] 一括導入の新規保存先、同一形状の再利用、失敗時の停止、既存Contentのハッシュ不変を模擬環境で検査
- [ ] WindowsでPlayしてAT/MTで発進・走行・停止・右左折を確認
- [ ] 既存試走レベル・車両データの回帰テストとログを記録

## 2026-11-24：Windows初回実行の修正

- 最初の実機ログで `install_takamatsu_stage1.ps1:89` の `& $python -I -m pip install ...` 呼び出しにより、Windows PowerShell 5.1が「インデックスが配列の境界外です」を報告。**UEエディターのクラッシュではなく、ライブラリ準備中の停止**。
- 旧地図アセットが消えたのではなく、インストーラーは `Recovery_Backup` から不足していた1086ファイル50点を復元し、`Build_001` と外部バックアップを確認済み。元のデータを再インポートせずに続行できる。
- 依存導入に`Maps/TakamatsuStage1/bootstrap_wheels.py`を追加。pipなしで公式PyPIの**2つの指定Windows wheel**を取得し、`requirements-win64.txt`に記録済みのハッシュと照合して、`Saved`に展開。UEインストール本体への変更・ユーザーの個人アセットへの書込なし。失敗時は修正対象のエラーを診断ログに記録。
- **修正後のWindows実機再試験は未実施。** GitHub DesktopでこのブランチをPullして、従来どおり `scripts/INSTALL_TAKAMATSU_STAGE1.cmd` をダブルクリックするだけ。以前の成功済みバックアップはそのまま再利用する。

## Windowsでの導入と実走確認

**この工程はユーザーのWindowsで一度に検証する。** ローカルの既存1086車両、試走場、個人アセットはバージョン管理外にある。GitHub Desktopが変更破棄・上書きを提案した場合は**Discardを選択しない**。前回の更新で作られた外部 `Recovery_Backup` が残っていることを確認する。マップインストーラーは、不足している1086アセットだけを外部バックアップから回収し（既存は上書きしない）、さらに **初回インストール時に1086 ContentとConfigの外部バックアップを作ってSHA-256で一致確認**する。Gitブランチ切替前のバックアップを置き換えるものではない。

一度の実機試験では、**①新規地図のタブ表示 ②AT前進・旋回・停止 ③完全MT半クラッチ発進・2速 ④自動クラッチMT発進 ⑤旧L_1086_DriveのAT走行 ⑥駅前の停車位置と進行方向 ⑦概要図・経路出典/欠測/フレームレート**まで確認する。エラー時は **`scripts/INSTALL_TAKAMATSU_STAGE1.cmd` が自動で診断レポートを開く**。成功後の不具合・位置ずれは `scripts/CHECK_TAKAMATSU_STAGE1.cmd` を一度ダブルクリックし、表示された `Saved/TakamatsuStage1/Stage1-Diagnostics.txt` とマップ画像を送る。UE上での運転操作は自動化されていないため、F310実走のみユーザーが行う。

1. 動作確認済みの1086号車があるプロジェクトでUEを保存して終了する。GitHub Desktopの **Current branch → feature/takamatsu-map-stage1** を選び、**Fetch origin → Pull origin**。**Repository → Show in Explorer** でその作業フォルダーを開く。
2. **scripts → INSTALL_TAKAMATSU_STAGE1.cmd** をダブルクリックする。初回はインターネットに接続する。**UE付属Pythonからpipは実行せず**、PyPI公式配布のNumPy 1.26.4・Shapely 2.1.2（Python 3.11 / Windows x64）をSHA-256で検証し、`Saved/TakamatsuStage1` にだけ展開する。続いて公式GTFS・OSMの照合、標高と建物データの取得、Development Editorのビルド、新規マップの生成が順に進む。UEが一度閉じてから通常のエディターが開く。**Blueprintの手動編集・車体の配置は不要**。
3. エディターのタブに **L_TakamatsuStation47** と表示されることを確認する。上部の **Play** の隣の **⋮ → Selected Viewport** を選び、**Play**。ゲーム画面をクリックする。マップにはPlayerStartが1つあり、レベルのGameModeが既存の1086号車をスポーンする。
4. **AT** ではHUDの **AT / N / Park ON** を確認。Aを押して停車保持、**1** でD、**Space** で駐車ブレーキ解除。Aを離して **RT** で発進、左スティックで旋回、**A** で停止する。**C** で車外から後輪・縁石の間隔を確認する。**K** で既存CSVの記録を開始・終了できる。
5. **MT** は停車・Park ONで **T**、**I** で始動。LTを踏んで **RB** で1速、Park解除後にLTを徐々に戻して発進する。停車・Park ONで再度Tを押すと自動クラッチMT。交差点への進入・後輪の内輪差・次停留所での停止を確認する。最後に **Esc → Content Drawer → Kotoden1086 → 使用中のBuild → L_1086_Drive** を開き、従来の試走場でも確認する。[既存の1086操作表](1086-MT.md)
6. `Saved/TakamatsuStage1/overview.svg` をブラウザーで開くと、実際に生成した三角形・経路・発進方向を平面で比較できる。`survey.json` に記録された次停留所名・経路の出所・乗場番号の根拠を確認する。信号位置、横断歩道、停止位置、沿道建物の一致、720pでのfpsを実機で記録する。

新しいアセットは `Content/TakamatsuRoute/Stage01/Build_<ID>` に保存する。データと生成コード・使用車両が同じときは前回のレベルを開き、変更や必要なパッケージの欠落があれば新規フォルダーを使う。中断時のフォルダーも上書きしない。初回のUE生成では、新しいレベルを再ロードしてGameModeを読み戻し、4輪の位置で道路メッシュにレイが当たることを検査する。

**失敗した場合**は診断レポート `Saved/TakamatsuStage1/Stage1-Diagnostics.txt` が自動で開くので、その1ファイルを共有する。必要なら `Saved/TakamatsuStage1/Runs/<ID>/install.log` と同フォルダーの `UnrealImport.log`、`result.json` を参照する。通信エラーではログのURLと入力ファイル名を確認する。正規の入力ファイルを `Inputs` に置いて再実行できる。⑤付近の道路・進行方向・車体の収まりが資料と一致しない場合はエラー内容と入力を保持する。UEのインストール先が標準外ならPowerShellで次を実行する。

```powershell
.\scripts\install_takamatsu_stage1.ps1 -UnrealRoot 'D:\Epic\UE_5.5'
```

クラウドで現行GTFS・OSM API・国土地理院・PLATEAUの配布先への接続はHTTP 403。歴史資料の比較値、推定値、利用条件、オフライン入力、生成器の検査範囲は別紙に記録した。[出典と精度、旧47系統と道路の比較図](../Maps/TakamatsuStage1/README.md)
