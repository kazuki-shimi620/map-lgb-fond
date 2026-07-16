# 周辺施設CSV仕様

病院、スーパー、商業施設、公園、コンビニの地図マーカーは、学習側で正規化したCSVから軽量JSONを生成し、ブラウザへ配信する。

ブラウザから外部POI APIを直接呼び出さない。実データは公式オープンデータ、配布条件が明確な公開データ、または手動で出典を記録したCSVだけを使う。

## 現在の対象エリア

周辺施設JSONはカテゴリごとに取得元と取得範囲が異なる。UIでは同じ「周辺施設」レイヤーとして表示するが、現時点で全国同一カバレッジではない。

| カテゴリ | 現在の対象エリア | 備考 |
| --- | --- | --- |
| 商業施設 | 全国元データ | JCSCオープンSC一覧は全国を対象にする。ただし地図マーカーはGeolonia町丁目代表点で緯度経度を付与できた行だけを出力する。 |
| 病院 | 首都圏4県（一都三県） | 不動産情報ライブラリ `XKT010` を首都圏4県z=13で取得したもの。全国取得は未実施。 |
| スーパー | 首都圏bbox | OpenStreetMap/Overpass APIを首都圏bboxで取得したもの。主対象は一都三県だが、bbox境界付近は周辺県を含む可能性がある。 |
| コンビニ | 首都圏bbox | OpenStreetMap/Overpass APIを首都圏bboxで取得したもの。主対象は一都三県だが、bbox境界付近は周辺県を含む可能性がある。 |
| 公園 | 首都圏4県（一都三県） | OpenStreetMap/Overpass APIを東京・神奈川・埼玉・千葉のbboxへ分割して取得したもの。大型公園面積は東京から部分取得中。 |

将来全国対応する場合は、病院・スーパー・コンビニ・公園を都道府県または地域ブロック単位で再取得し、metadataにカテゴリ別の対象エリアを残す。

## 入力CSV

テンプレート:

```text
training/data/manual/facilities/nearby_facilities_template.csv
```

標準の入力先:

```text
training/data/processed/facilities/nearby_facilities.csv
```

JCSC商業施設CSVに `lat` / `lon` を付与した場合は、`make nearby-facilities` 実行時に `commercial_facility` マーカーとして同じJSONへ取り込む。既定では、2015年以降のJCSCオープンSC CSVと、全国一覧PDF由来の補完CSVを併用する。

```text
training/data/processed/jcsc/jcsc_sc_open_with_coordinates.csv
training/data/processed/jcsc_pdf/jcsc_sc_pdf_new_candidates_with_coordinates.csv
```

緯度経度がない商業施設行、市区町村代表点の低信頼仮座標、`coordinate_confidence=low` の行は地図マーカーへ出力しない。市区町村/都道府県単位の集計やモデル比較には、住所未確定のPDF由来行も利用できる。

JCSC商業施設CSVへ町丁目代表点を付与する場合は、次を実行する。

```bash
make enrich-commercial-facilities
make enrich-sc-pdf-candidates
make nearby-facilities
```

2026-07-16時点では、旧JCSC CSVと全国一覧PDF由来データを統合し、商業施設サマリーは全国3,197件、47都道府県、884市区町村を保持する。座標ありは2,912件だが、このうち市区町村代表点を除いた信頼座標は211件で、`frontend/public/facilities/nearby_facilities.json` へ `commercial_facility` マーカーとして出力した。配信用サマリーJSONには `coverage` として、対象エリア、件数、座標付与率、信頼座標率、面積欠損率を記録する。

2026-07-15に不動産情報ライブラリ `XKT010` 医療機関APIの1タイル疎通を行い、医療機関210件を `hospital` マーカーとして出力した。その後、首都圏4県z=13の全域取得を実行し、59,066件の医療機関CSVと、重複排除後59,062件の `hospital` マーカーを `frontend/public/facilities/nearby_facilities.json` へ反映した。2026-07-16時点の周辺施設JSONは病院59,062件、商業施設211件、合計59,273件である。

```bash
make collect-medical-facilities-dry-run
make collect-medical-facilities-tile MEDICAL_REQUEST_INTERVAL_SECONDS=0
make collect-medical-facilities MEDICAL_REQUEST_INTERVAL_SECONDS=0.05
make nearby-facilities NEARBY_FACILITIES_INPUTS=data/processed/medical/nearby_medical_facilities.csv
```

スーパー、コンビニ、公園はOpenStreetMapのOverpass APIから取得する。OpenStreetMapデータはOpen Database License (ODbL) として扱う。2026-07-15時点では、スーパー6,345件、コンビニ17,190件、公園27,231件を取得し、病院・商業施設と合わせて合計109,972件、38MBの周辺施設JSONを生成した。表示側では周辺施設パネルにOpenStreetMap contributors (ODbL)への帰属リンクを出し、地図内マーカーは現在の表示範囲内かつ中心に近い最大1,200件へ制限して大量描画を避ける。

大型公園特徴量の検討用に、OSM公園取得は `--include-geometry` 指定時に `park_areas.csv` も出力する。way/relationの `geometry` がある場合は簡易投影のポリゴン面積、geometryがないrelation等は `bounds` の矩形面積を概算として保存する。2026-07-15に東京全域の `out geom` はOverpass 504となったため、`OSM_PARK_BBOX` で小bboxに分割する。疎通確認として `35.65 139.68 35.75 139.78` のbboxを実取得し、827公園マーカー・799面積行を生成した。また `--split-size-degrees` と `--continue-on-error` により、同bboxの4分割実取得で3セル成功・1セル429をmetadataへ記録し、575公園マーカー・549面積行を結合できることを確認した。東京全域0.1度グリッドは40セル中12セル成功・28セル失敗となり、2,801公園マーカー・2,717面積行を生成した。未取得セルは同じrun-idをキャッシュ付きで再実行して埋める。

```bash
make collect-osm-nearby-facilities-dry-run
make collect-osm-nearby-facilities OSM_NEARBY_CATEGORIES=supermarket
make collect-osm-nearby-facilities OSM_NEARBY_CATEGORIES=convenience_store
cd training && uv run python src/collect/osm_nearby_facilities.py --area tokyo --categories park --cache --run-id latest_park_tokyo --processed-dir data/processed/osm_nearby/park_tokyo
make collect-osm-park-areas OSM_PARK_AREA=tokyo_sample OSM_PARK_BBOX="35.65 139.68 35.75 139.78" OSM_PARK_RUN_ID=latest_park_tokyo_sample_geometry OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_sample_geometry
make collect-osm-park-areas OSM_PARK_AREA=tokyo_sample_grid OSM_PARK_BBOX="35.65 139.68 35.75 139.78" OSM_PARK_RUN_ID=latest_park_tokyo_sample_grid_geometry OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_sample_grid_geometry OSM_PARK_SPLIT_SIZE_DEGREES=0.05 OSM_PARK_CONTINUE_ON_ERROR=1
make collect-osm-park-areas OSM_PARK_AREA=tokyo OSM_PARK_RUN_ID=latest_park_tokyo_geometry_grid_010 OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_geometry_grid_010 OSM_PARK_SPLIT_SIZE_DEGREES=0.1 OSM_PARK_CONTINUE_ON_ERROR=1
make nearby-facilities NEARBY_FACILITIES_INPUTS="data/processed/medical/nearby_medical_facilities.csv data/processed/osm_nearby/supermarket/nearby_osm_facilities.csv data/processed/osm_nearby/convenience_store/nearby_osm_facilities.csv data/processed/osm_nearby/park_tokyo/nearby_osm_facilities.csv data/processed/osm_nearby/park_kanagawa/nearby_osm_facilities.csv data/processed/osm_nearby/park_saitama/nearby_osm_facilities.csv data/processed/osm_nearby/park_chiba/nearby_osm_facilities.csv" COMMERCIAL_FACILITIES_CSV=data/processed/jcsc/jcsc_sc_open_with_coordinates.csv
```

| column | required | description |
| --- | --- | --- |
| `id` | no | 空の場合はカテゴリ、施設名、緯度経度から自動生成する |
| `category_id` | yes | `hospital`, `supermarket`, `commercial_facility`, `park`, `convenience_store` |
| `name` | yes | 施設名 |
| `lat` | yes | 緯度 |
| `lon` | yes | 経度 |
| `prefecture` | no | 都道府県 |
| `municipality` | no | 市区町村 |
| `address` | no | 住所 |
| `source` | no | データ出典 |
| `updated_at` | no | データ更新日または確認日 |

## 生成

```bash
make nearby-facilities
```

出力:

```text
frontend/public/facilities/nearby_facilities.json
```

入力CSVが存在しない場合は、カテゴリ定義だけを含む未生成JSONを出力する。これにより、フロントエンドはデータ未投入の状態でも同じUIで動作する。

テンプレートを再生成する場合:

```bash
make nearby-facilities-template
```

## 実データ投入時の注意

大量POIをモデル特徴量へ直接入れない。モデルへ使う場合は、距離や半径件数に集計したうえで `docs/surrounding-features.md` の採用基準に沿って比較する。

周辺施設JSONは地図表示用の参考情報であり、価格を保証する情報として表示しない。
