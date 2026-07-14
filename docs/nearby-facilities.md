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
