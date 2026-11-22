# P0-3 Chaos 仮車両のセットアップと走行確認

UE 5.5.4 の [Vehicle テンプレート](https://dev.epicgames.com/documentation/en-us/unreal-engine/vehicle-template-in-unreal-engine?application_version=5.5) に同梱される4輪車の Skeletal Mesh、Physics Asset、Animation Blueprint、前後の Chaos Wheel Blueprint を使う。アセットは UE の利用条件に従い、Windows 側で移行する。リポジトリに車両アセットやレベルは含めていない。以下の初回設定を終えてから走行を試す。

## 1. ブランチを取得してビルドする

1. UE エディターを終了する。GitHub Desktop の **Fetch origin → Current Branch** で `p0/chaos-prototype-drive` に切り替え、**Pull origin** が出たら押す。
2. エクスプローラーで `KotodenBusSimulator.uproject` を右クリックし、**Generate Visual Studio project files** を選ぶ。
3. `KotodenBusSimulator.sln` を Visual Studio 2022 で開く。**Development Editor / Win64** を選択し、ソリューション エクスプローラーで **KotodenBusSimulator → 右クリック → ビルド**。エラーが出たらビルド出力の最初のエラーを控える。

## 2. 公式テンプレートの車両を取り込む

1. UE **5.5.4** を起動し、プロジェクトブラウザーで **Games → Vehicle → Blueprint → Create**。バリアント選択欄があれば標準の **None** を選び、シミュレーターとは別のフォルダーに一時プロジェクトを作る。Vehicle が一覧になければ、Epic Games Launcher のエンジンの **Options** から **Templates and Feature Packs** を追加する。
2. 一時プロジェクトで Play を押し、標準車両が動くことを確認して停止する。レベル内で標準車を選べる場合は Details のクラスから車両 Blueprint を開く。レベルに車が配置されていない場合は **Window → World Settings → GameMode Override** か **Edit → Project Settings → Maps & Modes** の既定 GameMode を調べ、その **Default Pawn Class** を Content Browser で探す。
3. Content Browser で見つけた実際にプレイで使う車両 Blueprint を右クリックする。**Asset Actions → Migrate** を選び、**Asset Report** で依存アセットにチェックが入ったまま **OK** を押す。保存先はシミュレーターの `KotodenBusSimulator.uproject` と同じ階層にある **Content** フォルダーを選ぶ。なければ作る。
4. シミュレーターを開き、取り込んだ車両 Blueprint を見つける。設定を参照するため、この Blueprint を開いたままにする。

## 3. F310 用の車両 Blueprint を作る

1. シミュレーターの **Content Drawer → Add → Blueprint Class → All Classes** で `BusPrototypeVehiclePawn` を検索して選択する。名前は `BP_F310Prototype` にする。
2. 両方の Blueprint の左上 **Components** で車体の **Mesh** を選び、テンプレートの Mesh が使用する **Skeletal Mesh Asset** と **Anim Class** を新しい Blueprint に設定する。**Animation Mode** は **Use Animation Blueprint**。Physics Asset は Skeletal Mesh の既定値を使い、テンプレートの Mesh に **Physics Asset Override** が設定されている場合は同じアセットを指定する。Mesh の **Simulate Physics** がオンであることと、コリジョンプリセットが **Vehicle** であることを確認する。
3. 両方の Blueprint で **Vehicle Movement Component** を選ぶ。テンプレートの **Wheel Setups**、**Engine Setup**、**Transmission Setup**、**Differential Setup**、**Steering Setup** を新しい Blueprint に写す。Details の項目名を右クリックし、**Copy / Paste** が使える場合は項目単位でコピーできる。表示されなければ項目を展開し、値を個別に合わせる。
4. **Wheel Setups** が4件あることを確認する。各要素の **Wheel Class**、**Bone Name**、**Additional Offset** はテンプレートと同じ順番・値にする。**Engine Setup** の **Torque Curve** も写し、外部カーブを使うテンプレートなら同じ Curve アセットを選ぶ。**Mechanical Sim Enabled** と **Automatic Transmission** をオン、**Automatic Reverse** がある場合はオフにする。**Reverse as Brake** がオフであることを確認する。
5. テンプレートの **Mass** などの車体設定を写す。**Class Defaults → Prototype Brake** の初期値は **Brake Rise Per Second** が `2.0`、**Brake Fall Per Second** が `3.0`（単位は正規化指令の変化量/秒）。Chaos 側の **Brake Input Rate** を調整する場合は、二重にゆっくり立ち上がるのを避けるため、C++ 側より十分速い線形のレート（例として Rise/Fall 各 `10`/秒）を使う。**Compile → Save** を押す。

新しい車両 Blueprint の Event Graph にテンプレートの入力イベントをコピーする必要はない。C++ の Pawn が P0-2 の入力を読み、内蔵の Spring Arm と Camera が追従する。

## 4. 平坦な走行レベルに割り当てる

1. **Content Drawer → Add → Blueprint Class → All Classes** で `BusInputGameMode` を選択し、`BP_F310DriveGameMode` を作る。**Class Defaults → Classes → Default Pawn Class** を `BP_F310Prototype` に変更する。**Player Controller Class** と **HUD Class** は継承した値を使う。**Compile → Save**。
2. **File → New Level → Basic → Create** で照明付きレベルを作成し、`L_F310FlatTest` として Content 内に保存する。広い平面を作るには、Outliner で既存の床を選んで削除し、**Place Actors → Shapes → Cube** を配置する。その Cube の **Details → Transform** で **Location (0, 0, -25)**、**Scale (200, 200, 0.5)** にする。標準の1 m Cube なら床は約200 m四方で上面が Z=0 cm。**Collision Presets** は **BlockAll** にする。
3. Outliner の **Player Start** を選び、床中央の真上（例 **Location (0, 0, 150)**、単位 cm）に置く。存在しなければ **Place Actors** で `Player Start` を検索して配置する。車両 Blueprint はレベルに配置せず、GameMode にスポーンさせる。
4. **Window → World Settings → GameMode Override** を **BP_F310DriveGameMode** に設定して、レベルを保存する。プロジェクト全体の既定 GameMode はそのままにする。これで `Entry` では引き続き P0-2 の診断が使える。

## 5. Play して確認する

1. F310 の背面スイッチを **X** にし、USB で接続する。エディターで `L_F310FlatTest` を開く。**Play** の横のメニューで **Default Player Start** を選び、**Play** を押してビューポート内をクリックする。**Simulate** ではプレイヤーとして操作できない。
2. 車体の後ろから表示され、シアン色の HUD に `P0-3 Chaos / F310`、`Forward speed`（前進方向の速度、km/h）、`Service brake`（指令、0〜1）が出ることを確認する。
3. RT を少しずつ押して発進・加速し、左スティックを左右に倒して旋回する。RT を離して A を短く押すとブレーキ指令は途中まで増え、長く押すと 1 に達する。A を保持して停止するまで速度が落ちること、停止後に後退しないこと、A を離すと指令が 0 に戻ることを確認する。
4. LT と LB/RB、右スティックも動かし、P0-2 の表示が反応することを確認する。これらは P0-3 では駆動やカメラの操作に接続していない。最後に `Entry` を開いて Play し、以前どおり `P0-2 F310 / XInput` が出ることを確認する。

車がスポーンせず P0-2 の表示が出る場合は、走行レベルの **GameMode Override**、GameMode の **Default Pawn Class**、**Player Start** の衝突を確認する。車体は出るが動かない場合は、床の衝突、Mesh の物理アセットと **Simulate Physics**、4輪の Bone Name、トルク曲線、**Automatic Transmission** を順に確認する。HUD の RT 自体が変化しなければ、ビューポートのフォーカス、F310 の X スイッチ、USB 接続を確認する。

## 調整と検証状況

- 車両質量（kg）・重心オフセットの上書き値（cm）・駆動方式（Differential Type）は **Vehicle Movement Component**。ホイールベース（cm）は前後輪のボーン間距離で決まり、試作では各 Wheel Setup の **Additional Offset** の X を前後輪ごとに変えて調整できる。見た目と一致させる場合は元の骨格配置も合わせる。車輪半径（cm）は前後の Chaos Wheel Blueprint の **Wheel Radius**。テンプレートへの影響を避ける場合は Wheel Blueprint を複製して仮車両の **Wheel Class** に指定する。
- 車体・エンジン・ギア比・タイヤの設定は Epic のテンプレートを出典とする仮値。ブレーキ時間とカメラ位置も走行確認用の仮値。Chaos 標準の自動変速は今回の走行検証に使う。独自 MT、クラッチ物理、正式車両、高松市マップ、乗客は対象外。
- P0-2 までのビルドと入力はユーザーの Windows で確認済み。P0-3 は **ビルド未実施 / UE実行未確認 / F310実機未検証**。上の手順で設定と走行を確認したら、ビルド結果、発進・左右旋回・停止・A 保持時に後退しないこと、ブレーキ指令の増減、P0-2 診断の結果を記録する。
