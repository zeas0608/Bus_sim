# 高松駅⑤番のりばと御厩線47番

対象は高松駅の出発位置から最初の停留所まで（上限550 m）。駅前広場と公道への接続を一緒に扱う。取得時の下り便から区間と進行方向を決め、道路、縁石、建物、信号を同じ座標に投影する。

## 出典と精度

| 資料 | 使用範囲・限界 |
|---|---|
| [ことでんバス・御厩線](https://www.kotoden.co.jp/publichtm/bus/rosen/yusa_mimaya/index.html)、[事業者のGTFS公開ページ](https://www.kotoden.co.jp/publichtm/gtfs/index.html) | 47番、高松駅⑤番はプロジェクト指定と既調査記録による。インストール時にバス用GTFSの運行日・方面・停留所順・位置・経路形状を照合する。乗場の緯度経度と車体中心を区別する。利用は個人のローカル環境。原本・写真・時刻表の再配布を行わない。公開条件は配布元を参照。 |
| [国土数値情報の旧バスルートをGeoJSON化した資料](https://github.com/handygeospatial/ksj/blob/f1815c26a92cb1efdb66419e331a329c87f93ea9/N07/N07-11_37.geojson) | 2011年香川県の「ことでんバス（株）／御厩・県立プール線47」は、駅前を回り東寄りの道路へ出て南下する線形を持つ。2026-11-23に属性・線形を閲覧。現行の出口・車線・停車位置を確定するための資料には使わない。 |
| [国土数値情報・バス停留所2022年の加工表](https://github.com/tomtkg/Japanese-Bus-Stop-Data/blob/c4741e649c979b52a507fd695756fcac1373422c/prefectures/37_Kagawa.csv) | 高松駅、高松築港に御厩線の記載を確認。表に停留所の順序や車線座標は含まれない。 |
| [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) | 道路・一方通行・道路幅/車線数・歩道・プラットフォーム・交差点・横断歩道・信号ノード・建物輪郭。ODbL 1.0。データは取得時の地図であり現地測量ではない。元のOSM IDと利用した属性を記録。派生データを外部配布する場合はODbLの帰属・データ提供条件を確認する。 |
| [PLATEAU高松市2022年](https://www.geospatial.jp/ckan/dataset/plateau-37201-takamatsu-shi-2022)、[公開モデルの利用条件](https://www.mlit.go.jp/plateau/open-data/) | 建築物LOD1の地表輪郭・高さを優先するための資料。年度・範囲は運行経路と別。利用時は個別データの出典と許諾を記録する。テクスチャ・航空写真は使用しない。 |
| [地理院タイル一覧・標高](https://maps.gsi.go.jp/development/ichiran.html#dem)、[国土地理院コンテンツ利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html) | 10 mメッシュ標高を地域の起伏に用いる。格子からの補間値で、バスベイの縁石高や舗装面の測量値ではない。 |

原点は東経134.0474°、北緯34.3517°の計算上の基準点。WGS84楕円体から局所接平面に投影し、UEではXが北、Yが東、Zが上、1 m = 100 cm。公開元が到達不能なクラウドでは、現行GTFS・OSM・標高の取得に成功したとは扱わない。出典や精度は生成時の記録と合わせて確認する。
