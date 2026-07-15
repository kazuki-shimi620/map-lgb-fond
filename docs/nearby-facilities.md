# 周辺施設CSV仕様

病院、スーパー、商業施設、公園、コンビニの地図マーカーは、学習側で正規化したCSVから軽量JSONを生成し、ブラウザへ配信する。

ブラウザから外部POI APIを直接呼び出さない。実データは公式オープンデータ、配布条件が明確な公開データ、または手動で出典を記録したCSVだけを使う。

## 入力CSV

テンプレート:

```text
training/data/manual/facilities/nearby_facilities_template.csv
```

標準の入力先:

```text
training/data/processed/facilities/nearby_facilities.csv
```

JCSC商業施設CSVに `lat` / `lon` を付与した場合は、`make nearby-facilities` 実行時に `commercial_facility` マーカーとして同じJSONへ取り込む。既定の参照先は次の通り。

```text
training/data/processed/jcsc/jcsc_sc_open.csv
```

緯度経度がない商業施設行は地図マーカーへ出力しない。

JCSC商業施設CSVへ町丁目代表点を付与する場合は、次を実行する。

```bash
make enrich-commercial-facilities
make nearby-facilities COMMERCIAL_FACILITIES_CSV=data/processed/jcsc/jcsc_sc_open_with_coordinates.csv
```

2026-07-15時点では、Geolonia住所データの町丁目代表点により429件中144件へ代表座標を付与し、`frontend/public/facilities/nearby_facilities.json` へ `commercial_facility` マーカーとして出力した。町丁目代表点のため、施設入口や建物中心点の精密座標ではない。

同日に不動産情報ライブラリ `XKT010` 医療機関APIの1タイル疎通を行い、医療機関210件を `hospital` マーカーとして出力した。その後、首都圏4県z=13の全域取得を実行し、59,066件の医療機関CSVと、重複排除後59,062件の `hospital` マーカーを `frontend/public/facilities/nearby_facilities.json` へ反映した。周辺施設JSONは病院59,062件、商業施設144件、合計59,206件、24MBである。

```bash
make collect-medical-facilities-dry-run
make collect-medical-facilities-tile MEDICAL_REQUEST_INTERVAL_SECONDS=0
make collect-medical-facilities MEDICAL_REQUEST_INTERVAL_SECONDS=0.05
make nearby-facilities NEARBY_FACILITIES_CSV=data/processed/medical/nearby_medical_facilities.csv COMMERCIAL_FACILITIES_CSV=data/processed/jcsc/jcsc_sc_open_with_coordinates.csv
```

スーパー、コンビニ、公園はOpenStreetMapのOverpass APIから取得する。OpenStreetMapデータはOpen Database License (ODbL) として扱う。2026-07-15時点では、スーパー6,345件、コンビニ17,190件、公園27,231件を取得し、病院・商業施設と合わせて合計109,972件、38MBの周辺施設JSONを生成した。表示側では周辺施設パネルにOpenStreetMap contributors (ODbL)への帰属リンクを出し、地図内マーカーは現在の表示範囲内かつ中心に近い最大1,200件へ制限して大量描画を避ける。

大型公園特徴量の検討用に、OSM公園取得は `--include-geometry` 指定時に `park_areas.csv` も出力する。way/relationの `geometry` がある場合は簡易投影のポリゴン面積、geometryがないrelation等は `bounds` の矩形面積を概算として保存する。2026-07-15に東京全域の `out geom` はOverpass 504となったため、`OSM_PARK_BBOX` で小bboxに分割する。疎通確認として `35.65 139.68 35.75 139.78` のbboxを実取得し、827公園マーカー・799面積行を生成した。また `--split-size-degrees` と `--continue-on-error` により、同bboxの4分割実取得で3セル成功・1セル429をmetadataへ記録し、575公園マーカー・549面積行を結合できることを確認した。

```bash
make collect-osm-nearby-facilities-dry-run
make collect-osm-nearby-facilities OSM_NEARBY_CATEGORIES=supermarket
make collect-osm-nearby-facilities OSM_NEARBY_CATEGORIES=convenience_store
cd training && uv run python src/collect/osm_nearby_facilities.py --area tokyo --categories park --cache --run-id latest_park_tokyo --processed-dir data/processed/osm_nearby/park_tokyo
make collect-osm-park-areas OSM_PARK_AREA=tokyo_sample OSM_PARK_BBOX="35.65 139.68 35.75 139.78" OSM_PARK_RUN_ID=latest_park_tokyo_sample_geometry OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_sample_geometry
make collect-osm-park-areas OSM_PARK_AREA=tokyo_sample_grid OSM_PARK_BBOX="35.65 139.68 35.75 139.78" OSM_PARK_RUN_ID=latest_park_tokyo_sample_grid_geometry OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_sample_grid_geometry OSM_PARK_SPLIT_SIZE_DEGREES=0.05 OSM_PARK_CONTINUE_ON_ERROR=1
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
