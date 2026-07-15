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

同日に不動産情報ライブラリ `XKT010` 医療機関APIの1タイル疎通を行い、医療機関210件を `hospital` マーカーとして出力した。首都圏全域取得は `make collect-medical-facilities` で実行できるが、z=13では2,160リクエストになるため、長時間ジョブとして扱う。

```bash
make collect-medical-facilities-dry-run
make collect-medical-facilities-tile MEDICAL_REQUEST_INTERVAL_SECONDS=0
make nearby-facilities NEARBY_FACILITIES_CSV=data/processed/medical/nearby_medical_facilities.csv COMMERCIAL_FACILITIES_CSV=data/processed/jcsc/jcsc_sc_open_with_coordinates.csv
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
