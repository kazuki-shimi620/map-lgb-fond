# 周辺施設CSV仕様

商業施設の地図マーカーは、学習側で正規化したCSVから軽量JSONを生成し、ブラウザへ配信する。

ブラウザから外部POI APIを直接呼び出さない。実データは公式オープンデータ、配布条件が明確な公開データ、または手動で出典を記録したCSVだけを使う。

## 地図表示の対象

中古マンション売買では都市部が主対象になるため、件数が多く都市部での情報価値が限定的なPOIは地図へ配信しない。データ量、描画負荷、継続的な更新コストを抑えるため、標準の配信対象は商業施設と、件数を限定できる映画館・温浴施設・美術館・博物館とする。

| カテゴリ | 方針 | 備考 |
| --- | --- | --- |
| 商業施設 | 表示する | JCSC公開PDF・年別ページを基に独自生成した全国データのうち、信頼できる緯度経度がある施設だけを出力する。 |
| 映画館、温泉、美術館・博物館 | 表示する | OSMから全国を地域分割して取得し、カテゴリ別にON/OFFできる参考情報として配信する。 |
| 病院、コンビニ、スーパー、ドラッグストア、飲食店など | 表示しない | 件数、配信サイズ、更新負荷が大きく、都市部では位置情報の差別化価値が限定的なため。 |
| 公園 | 大型公園だけ将来検討 | 小規模公園の全件マーカーは配信しない。 |

### 現行配信スナップショット

`frontend/public/facilities/nearby_facilities.json` の2026-08-01生成分は、全国の
商業施設2,911件、映画館520件、美術館・博物館7,269件、温泉・入浴施設2,969件、
合計13,669件を保持する。これを現行UIと配信容量の基準とし、以下の過去スナップショットは
収集・軽量化の判断履歴として扱う。

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

### 生成構成の変遷

以下の件数は当時の生成結果であり、現在配信中のカテゴリ・件数ではない。

2026-07-16時点では、旧JCSC CSVと全国一覧PDF由来データを統合し、商業施設サマリーは全国3,197件、47都道府県、884市区町村を保持する。座標ありは2,912件だが、このうち市区町村代表点を除いた信頼座標は211件で、`frontend/public/facilities/nearby_facilities.json` へ `commercial_facility` マーカーとして出力した。配信用サマリーJSONには `coverage` として、対象エリア、件数、座標付与率、信頼座標率、面積欠損率を記録する。

2026-07-15に不動産情報ライブラリ `XKT010` 医療機関APIの1タイル疎通を行い、医療機関210件を `hospital` マーカーとして出力した。その後、首都圏4県z=13の全域取得を実行し、59,066件の医療機関CSVと、重複排除後59,062件の `hospital` マーカーを `frontend/public/facilities/nearby_facilities.json` へ反映した。2026-07-16時点の周辺施設JSONは病院59,062件、商業施設211件、合計59,273件である。

```bash
make collect-medical-facilities-dry-run
make collect-medical-facilities-tile MEDICAL_REQUEST_INTERVAL_SECONDS=0
make collect-medical-facilities MEDICAL_REQUEST_INTERVAL_SECONDS=0.05
make nearby-facilities NEARBY_FACILITIES_INPUTS=data/processed/medical/nearby_medical_facilities.csv
```

スーパー、コンビニ、公園はOpenStreetMapのOverpass APIから取得する。OpenStreetMapデータはOpen Database License (ODbL) として扱う。2026-07-15時点では、スーパー6,345件、コンビニ17,190件、公園27,231件を取得し、病院・商業施設と合わせて合計109,972件、38MBの周辺施設JSONを生成した。表示側では周辺施設パネルにOpenStreetMap contributors (ODbL)への帰属リンクを出し、地図内マーカーは現在の表示範囲内かつ中心に近い最大1,200件へ制限して大量描画を避ける。

2026-07-28に首都圏4都県の映画館・温浴施設を1回のOverpassクエリで取得した。
映画館170件、温泉・公衆浴場・スパ914件を、商業施設2,911件と合わせて配信する。
周辺施設JSONは合計3,995件、約1.5MBであり、大量POIを配信していた構成より
十分小さい。スマホでは検索欄下のカテゴリボタンから個別にON/OFFできる。
ズーム10以下では約72px四方かつカテゴリごとに施設をクラスタ化し、カテゴリ色を維持した
まま、件数が多いほど大きく濃い円で表示する。異なるカテゴリの円は重なりを許容する。
ズーム11以上では施設ごとのマーカーへ切り替える。

```bash
cd training
uv run python src/collect/osm_nearby_facilities.py \
  --area capital \
  --categories cinema,hot_spring \
  --cache \
  --run-id latest_entertainment_capital \
  --processed-dir data/processed/osm_nearby/entertainment_capital
cd ..
make nearby-facilities \
  NEARBY_FACILITIES_INPUTS=data/processed/osm_nearby/entertainment_capital/nearby_osm_facilities.csv
```

### 映画館・温浴施設の全国化方針

2026-07-28に、施設本体をダウンロードしないOverpassの`out count`を1回実行した。
日本国内のOSM登録数は映画館520件、温浴系5,906件だった。映画館は名称付きが
505件で、名称付き率は97.1%だった。

これは実在施設の総数ではない。厚生労働省「令和6年度衛生行政報告例」では、
2024年度末の映画館は1,468施設、公衆浴場は23,668施設であり、定義の違いを
考慮してもOSMは網羅データではない。また、日本映画製作者連盟の2025年集計は
3,697スクリーンであり、施設数ではないため地図マーカー件数と直接比較しない。

全国データ取得では、トークン消費と失敗時の再取得量を抑えるため次の順序にする。

1. LLMや検索APIを施設ごとに呼ばず、OverpassクエリとPython正規化だけを使う。
2. 全国一括クエリはタイムアウトしたため、47都道府県単位で映画館・温浴施設を
   同時取得し、都道府県ごとのraw JSONをキャッシュする。
3. OSMのtype/idで全国重複排除し、名称がある行を標準配信対象にする。
4. metadataへOSM登録総数、名称付き件数、公式統計総数、対象地域、取得日時を記録する。
5. 公式統計は総数の監査に使い、名称・座標を持たない集計値からマーカーを生成しない。
6. Google Placesなど有料・再配布制約のある検索や、施設ごとのAI確認は採用しない。

この方法なら外部通信は最大47回、LLMによるデータ解釈は0回で、途中失敗時も該当する
都道府県だけ再実行できる。OSM不足分は、再配布可能な自治体・業界の一覧データが
見つかった都道府県だけ、決定的なCSV変換処理として追加する。

#### 大型映画館の優先補完計画

映画館は厚生労働省の施設総数1,468件を全件マーカー化するのではなく、
日本映画製作者連盟がシネコンの目安としている「同一所在地に5スクリーン以上」を
大型館の基本基準にする。スクリーン数が取得できない場合でも、大型商業施設への
併設が公式住所・施設名から確認できる館は対象に含める。

収集優先順位:

1. イオンシネマ、TOHOシネマズ、ローソン・ユナイテッドシネマ、
   松竹マルチプレックスシアターズ、109シネマズ、T・ジョイ、
   シネマサンシャインなど、全国・広域チェーンの公式劇場一覧。
2. コロナシネマワールド、USシネマなど地域チェーンの公式一覧。
3. OSMの`amenity=cinema`にだけ存在する映画館。個人館・単館系はこの段階で補完する。
4. 上記で不足する大型館だけを手動レビューする。施設単位の一般Web検索は原則行わない。

公式一覧はチェーンごとに一覧ページ、公開PDF、JSON-LD、サイト内APIの順で確認し、
最も少ないリクエストで全劇場を取得できる経路を選ぶ。各劇場ページは住所や
スクリーン数が一覧にない場合だけ取得する。raw HTML/PDFをチェーン単位でキャッシュし、
更新時は差分があるソースだけ再処理する。

2026-07-28時点で、一覧ページ1件ずつを使う
`training/src/collect/cinema_chains.py`を追加した。イオンシネマ99館、
TOHOシネマズ74館、ローソン・ユナイテッドシネマ39館の営業中計212館を
共通CSVへ変換する（公式ページ内の閉館済み4館は除外）。ユナイテッドは同じ一覧から住所、併設施設名、
スクリーン数、総席数も取得する。イオンとTOHOの住所は各館ページを
一括巡回せず、まずOSM・JCSCとの名称照合を行い、未照合館だけを取得対象にする。
さらに松竹マルチプレックスシアターズ25館（パートナー館2館を含む）、
109シネマズ20館、T・ジョイ20館、シネマサンシャイン17館を追加し、
公式7系列の営業中計294館へ拡張した。109シネマズは公式メディアガイドPDF
1件から全20館の住所・スクリーン数・席数を取得し、全館が5スクリーン以上である。
他3系列もそれぞれ公式一覧HTML 1件をキャッシュするため、施設ごとのアクセスは
発生しない。

```bash
make collect-cinema-chains
make collect-cinema-osm-national
make enrich-cinemas
```

`make enrich-cinemas` は未照合館の全件CSVに加え、5スクリーン以上または
大型商業施設併設情報を持つ館だけを抽出した
`training/data/processed/cinemas/official_chain_cinemas_priority_review.csv` を生成する。
施設単位の追加調査はこの優先CSVに限定し、全未照合館を手動検索しない。

優先レビュー館は公式住所をNominatimで座標化する。dry-runで対象件数を確認してから
1秒間隔で取得し、レスポンスを映画館ID・クエリ単位でキャッシュする。住所全文で候補が
ない場合だけ施設名と都道府県へフォールバックし、都道府県不一致の候補は採用しない。
さらに併設施設名の表記揺れを正規化し、市区町村一致を必須とする。NominatimとJCSCの
どちらにも候補がない場合だけ、公式ページの地図リンク座標を
`training/data/manual/cinemas/cinema_coordinates.csv` に記録する。

```bash
make collect-cinema-coordinates-dry-run
make collect-cinema-coordinates
make enrich-cinemas
```

日本の外接矩形による取得では1,171要素が返ったが、韓国など国外施設を含むため
全国件数としては不採用とした。その後、日本のOSM行政区域IDを直接指定する
1リクエスト方式で国内520要素の取得に成功した。地図用JSONには全国520要素を採用し、
首都圏版との重複はOSM IDで除去する。OSM未登録館もあるため、全国の全映画館を
網羅する件数とは扱わない。地図用JSONは映画館520件、商業施設2,911件、
温泉・入浴施設を統合して配信する。全国温浴施設は3条件の一括取得がタイムアウト
したため、公衆浴場node 2,305要素、天然温泉267要素、スパ0要素へ分割した。
首都圏については既取得のway/relationも残し、OSM IDで重複を除去する。
全国の公衆浴場way/relationは未取得なので、全施設を網羅する件数とは扱わない。
統合後の地図用JSONは温泉・入浴施設2,969件（首都圏外2,055件）、
映画館520件、商業施設2,911件の計6,400件となる。照合処理では
町丁目代表点と自治体代表点を採用しない。

### 美術館・博物館

公園は背景地図からも位置や規模を把握しやすいため、美術館・博物館を先に地図カテゴリ化する。
OSMの`tourism=museum`と`tourism=gallery`を対象とし、LLMや施設単位のWeb検索は使わない。

全国一括取得はOverpass APIでタイムアウトするため、北海道、東北、関東、中部、近畿、
中国、四国、九州、沖縄の9地方を0.5〜1度のグリッドへ分割する。raw JSONはセル単位で
キャッシュし、失敗時は未取得セルだけを再実行する。

```bash
make collect-museums-national
make nearby-facilities
```

2026-07-30のキャッシュ再実行では、Overpass APIで失敗したセルを115件から0件まで削減し、
地方境界の重複を除いた7,269件を地図用JSONへ反映した。統合後の地図用JSONは
美術館・博物館7,269件、映画館520件、温泉・入浴施設2,969件、商業施設2,911件の
計13,669件である。

商業施設マーカーは店舗面積を基準に4段階の規模を保持し、地図ツールチップへ
日本語ラベルを表示する。2026-08-01の配信対象2,911件は、小規模351件、中規模
1,307件、大規模884件、超大型274件、規模不明95件である。

地図の表示フィルターでは、商業施設の規模に加え、美術館・博物館、温浴施設、
映画館を利用目的に近い2〜3区分へ分ける。現行のOSM配信CSVには細分類タグを保持して
いないため、名称による保守的な分類を行い、判別不能な施設は「その他」に含める。

正規化項目:

```text
cinema_id
name
operator
prefecture
municipality
address
mall_name
screen_count
seat_count
lat
lon
coordinate_source
source_url
confirmed_at
```

座標は、公式住所とOSM映画館の正規化名称・住所一致、JCSC商業施設との
併設施設名・住所一致、既存住所マスタの順で補完する。町丁目代表点だけの座標は
地図マーカーに採用せず、公式一覧上の大型館としてcoverageには残す。

完了条件:

* 対象にした大手・広域チェーンの公式掲載館を100% CSVへ収録する。
* 5スクリーン以上と判定できる館について、名称・住所・出典URLを100%保持する。
* 座標確定率、OSM既存率、JCSC併設一致率、未照合件数をレポートする。
* 未照合レビューは大型館だけに絞り、AIによる施設ごとの検索・判定を行わない。

大型公園特徴量の検討用に、OSM公園取得は `--include-geometry` 指定時に `park_areas.csv` も出力する。way/relationの `geometry` がある場合は簡易投影のポリゴン面積、geometryがないrelation等は `bounds` の矩形面積を概算として保存する。2026-07-15に東京全域の `out geom` はOverpass 504となったため、`OSM_PARK_BBOX` で小bboxに分割する。疎通確認として `35.65 139.68 35.75 139.78` のbboxを実取得し、827公園マーカー・799面積行を生成した。また `--split-size-degrees` と `--continue-on-error` により、同bboxの4分割実取得で3セル成功・1セル429をmetadataへ記録し、575公園マーカー・549面積行を結合できることを確認した。東京全域0.1度グリッドは40セル中12セル成功・28セル失敗となり、2,801公園マーカー・2,717面積行を生成した。未取得セルは同じrun-idをキャッシュ付きで再実行して埋める。

再開時は同じbbox、分割幅、run-idを指定する。成功セルのraw JSONは `--cache` により再利用され、失敗セルだけがOverpassへ再要求される。リクエスト間隔はキャッシュ読込を除く実ネットワーク要求の開始間隔に適用し、HTTPエラー後も次の要求まで待機する。429を避けるため、広域取得では0.05〜0.1度グリッド、5秒以上のリクエスト間隔、`--continue-on-error` を初期値とし、metadataの `errorCount` が0になるまで間隔を空けて再実行する。bboxや分割幅を変える場合は、異なるrun-idを使って異なるセルのキャッシュを誤用しない。

東京都内の `35.65 139.68 35.75 139.78` サンプル799件を `summarize-osm-park-areas` で集計した結果、面積中央値は730.14㎡、90パーセンタイルは7,202.15㎡、95パーセンタイルは19,071.84㎡だった。2万㎡以上は39件（4.9%）、5万㎡以上は19件（2.4%）である。初回比較では2万㎡以上を大型公園とし、1万㎡と5万㎡を感度分析する。面積の採用対象は `area_source=geometry` に限定し、外接矩形で過大評価し得る `bounds` はcoverage確認と参考表示だけに使う。

この結果は東京都心部の一部に限られる。首都圏全域の `park_areas.csv` 生成は、まず既存取引座標へサンプル結合し、2万㎡しきい値の距離・件数に追加効果がある場合だけ実行する。

2026-08-11に、取得bboxの端から3kmを除いた東京都心サンプル9,987件・97地点で、2015年以降を学習、2023〜2025年を年別holdoutとして比較した。geometry面積2万㎡以上の26公園から、最寄距離、1km件数、3km件数を追加すると、3年すべてでMAE、RMSE、MAPEが改善した。加重MAEは6,426,202円から6,385,640円へ40,562円、RMSEは8,816,537円から8,757,284円へ59,253円改善した。

これは狭い都心範囲の97地点に限るため、本番採用の根拠にはしない。一方、首都圏全件取得へ進む最低条件は満たした。次は0.1度グリッドのセル数、最低5秒間隔の初回所要時間、429/504の再試行回数を見積もり、実行方針を確認してから取得する。比較時は1万㎡、2万㎡、5万㎡の感度分析と4都県・3評価年の指標を残す。

### 首都圏geometry取得コスト

2026-08-11に既存bboxを0.1度グリッドでdry-run計算した。都県別にrun-idと出力先を分け、境界重複はOSMのtype/idで統合時に除去する。

| 対象 | bbox | セル数 |
| --- | --- | ---: |
| 東京 | `35.5 139.0 35.9 140.0` | 40 |
| 神奈川 | `35.0 138.9 35.7 139.8` | 63 |
| 埼玉 | `35.75 138.7 36.3 139.9` | 72 |
| 千葉 | `34.9 139.7 36.2 140.9` | 156 |
| 合計 | - | 331 |

5秒間隔だけで初回の待機時間は約27.6分となる。Overpassの応答時間を含む初回は30〜60分、429・504・timeoutの失敗セルを再試行する全体は1〜3時間を見込む。東京の過去成功12セルはraw JSON合計約3.35MB、平均約0.28MBだったため、331セルのrawキャッシュは約90MBを中心値とし、密集地域や再試行を考慮した上限目安を180MBとする。

外部リクエストは初回331回が下限である。失敗セルだけを最大3回再試行する運用では、想定331〜700回、理論上限1,324回となる。ただし同一パスで失敗率が下がらない場合は打ち切り、間隔またはセル幅を見直す。実行条件は次とする。

* 都県ごとに別run-id、0.1度グリッド、5秒間隔、`--continue-on-error --cache` で開始する
* 1都県ずつ実行し、metadataの成功セル数、失敗理由、raw容量を確認してから次へ進む
* 再実行は同じrun-idを使い、成功済みセルをキャッシュから読む
* 429が続く場合はその日の実行を止め、10秒間隔で別日に再開する
* 504が特定セルで続く場合だけ、そのセルを0.05度へ分割して別run-idで取得する
* 各都県で `errorCount=0` または未取得範囲と打ち切り理由を記録してから結合する
* 生成物はGit管理せず、件数、coverage、取得日時、コマンド、容量をレポートへ残す

本取得と4都県バックテストは長時間処理となるため、この見積もりを確認してから実行する。

### 首都圏取得進捗

2026-08-11に東京40セルを、既存12セルのキャッシュから再開して5秒間隔で実行した。28セルまで成功し、公園8,967件、面積行8,722件を結合した。未取得は12セルで、内訳はHTTP 504が11セル、HTTP 429が1セルだった。raw JSONは成功28セル分を保持し、processed出力は約1.8MBとなった。

429を検出したため同日の追加取得は停止した。次回は同じrun-idを10秒間隔で再実行し、429セルを含む未取得分を再試行する。それでも504になるセルだけ0.05度bboxへ分割する。東京の未取得が解消するか打ち切り理由を確定するまでは、神奈川・埼玉・千葉の取得を始めない。

同日、再開処理のリクエスト間隔を、キャッシュ読込を除く実ネットワーク要求間だけに適用し、HTTPエラー後も待機するよう修正した。10秒間隔で12セルを再試行した結果、8セルが回復し、公園11,516件、面積行11,192件となった。残る504の4セルをそれぞれ0.05度の4サブセルへ分割し、同じrun-idで2回まで再試行した。16サブセル中11件は成功し、5件は2回連続で504だったため、API負荷を避けて当日の取得を停止した。

0.1度の成功36セルと0.05度の成功11サブセルを単純統合し、OSMのtype/idで重複34件を除くと、公園13,297件、面積行12,942件となる。rawキャッシュは47ファイル、約15.5MBである。未取得は `r00_c05` 内2件、`r01_c07` 内1件、`r01_c09` 内2件の合計5サブセルである。次回は別日に同じ0.05度run-idを10秒間隔で再実行し、`errorCount=0` を確認してから東京の成果物へ統合する。

統合には `merge-osm-park-areas` を使う。0.1度成果物を入力に含め、その4エラーは0.05度成果物で置換済みとして `supersededErrors` に残す。0.05度の4出力を `OSM_PARK_MERGE_ERROR_SOURCE_DIRS` に指定すると、未解消エラーだけが統合metadataの `errors` と `errorCount` に反映される。CSVはOSMのtype/id由来の `id` で重複排除するため、境界上の公園を二重計上しない。通常は未解消エラーが1件でもあれば統合を失敗させる。調査用の部分成果物だけ `OSM_PARK_MERGE_ALLOW_ERRORS=1` で明示的に許可する。現在の部分成果物で統合コマンドを検証し、公園13,297件、面積行12,942件、未解消5件がmetadataと一致することを確認した。

その後の再試行で0.05度の未取得は3セルまで減った。対象だけを0.025度へ分割して2回取得し、さらに残った3セルを0.0125度へ分割した。最深層では12セル中6件が成功し、6件が504となった。取得済みの全階層を統合すると、公園13,940件、面積行13,560件、未解消6件、置換済み上位エラー10件となる。最終再試行は実行権限確認が2回タイムアウトし、API要求を送信できなかったため、同じ0.0125度run-idから再開する。

再開後、最深層の6セル中5件が回復し、最後の1セルも追加再試行で成功した。このセルは正常応答で公園要素0件だった。全階層を完成版として統合し、完了ゲートが `errorCount=0` で通ることを確認した。東京の確定成果物は公園13,976件、面積行13,596件で、`park_areas.csv` は約1.62MB、置換済み上位エラーは10件である。

東京完了後、神奈川63セルを0.1度・5秒間隔で初回取得した。40セルが成功し、公園4,811件、面積行4,323件、rawキャッシュ40ファイル・約5.72MBとなった。未取得23セルの内訳はHTTP 504が3件、HTTP 429が9件、接続切断等の通信エラーが11件だった。429を検出したため当日の再試行を停止した。次回は同じrun-idを使って10秒間隔で23セルだけを再試行し、神奈川の完了または継続504セルの分割方針を確定してから埼玉へ進む。

10秒間隔で未取得23セルを再試行したが、23件すべてが `Errno 61 Connection refused` となり、成功数は40セルから増えなかった。特定bboxの504ではなくOverpassエンドポイント全体の接続拒否であるため、セルの追加分割は行わない。エンドポイントの復旧後に同じrun-idで再開し、成功キャッシュ40セルを再利用する。

疎通確認では `overpass-api.de` に加え、OpenStreetMap Wiki掲載の公式バックエンド `lz4.overpass-api.de` と `z.overpass-api.de` のstatusもすべて接続拒否だった。`OSM_NEARBY_ENDPOINT` でMakeコマンドの接続先を上書きできるようにしたが、公式掲載外の第三者インスタンスへ無断で大量取得を切り替えない。公式バックエンドのいずれかが復旧してから再開する。

公式statusの復旧と空きスロット2件を確認後、同じrun-id・10秒間隔で再開した。7セルが回復し、47/63セル、公園6,225件、面積行5,680件となった。残る16セルは通信エラー14件とHTTP 429が2件で、429再検出のため追加再試行を停止した。

```bash
make collect-osm-nearby-facilities-dry-run
make collect-osm-nearby-facilities OSM_NEARBY_CATEGORIES=supermarket
make collect-osm-nearby-facilities OSM_NEARBY_CATEGORIES=convenience_store
cd training && uv run python src/collect/osm_nearby_facilities.py --area tokyo --categories park --cache --run-id latest_park_tokyo --processed-dir data/processed/osm_nearby/park_tokyo
make collect-osm-park-areas OSM_PARK_AREA=tokyo_sample OSM_PARK_BBOX="35.65 139.68 35.75 139.78" OSM_PARK_RUN_ID=latest_park_tokyo_sample_geometry OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_sample_geometry
make collect-osm-park-areas OSM_PARK_AREA=tokyo_sample_grid OSM_PARK_BBOX="35.65 139.68 35.75 139.78" OSM_PARK_RUN_ID=latest_park_tokyo_sample_grid_geometry OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_sample_grid_geometry OSM_PARK_SPLIT_SIZE_DEGREES=0.05 OSM_PARK_CONTINUE_ON_ERROR=1
make collect-osm-park-areas OSM_PARK_AREA=tokyo OSM_PARK_RUN_ID=latest_park_tokyo_geometry_grid_010 OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_geometry_grid_010 OSM_PARK_SPLIT_SIZE_DEGREES=0.1 OSM_PARK_CONTINUE_ON_ERROR=1
make merge-osm-park-areas OSM_PARK_MERGE_INPUT_DIRS="data/processed/osm_nearby/park_tokyo_geometry_grid_010 data/processed/osm_nearby/park_tokyo_r00_c05_geometry_grid_005 data/processed/osm_nearby/park_tokyo_r01_c07_geometry_grid_005 data/processed/osm_nearby/park_tokyo_r01_c09_geometry_grid_005 data/processed/osm_nearby/park_tokyo_r02_c05_geometry_grid_005" OSM_PARK_MERGE_ERROR_SOURCE_DIRS="data/processed/osm_nearby/park_tokyo_r00_c05_geometry_grid_005 data/processed/osm_nearby/park_tokyo_r01_c07_geometry_grid_005 data/processed/osm_nearby/park_tokyo_r01_c09_geometry_grid_005 data/processed/osm_nearby/park_tokyo_r02_c05_geometry_grid_005" OSM_PARK_MERGE_OUTPUT_DIR=data/processed/osm_nearby/park_tokyo_geometry_merged OSM_PARK_MERGE_ALLOW_ERRORS=1
make summarize-osm-park-areas OSM_PARK_PROCESSED_DIR=data/processed/osm_nearby/park_tokyo_sample_geometry
make compare-large-park-features-dry-run
make nearby-facilities NEARBY_FACILITIES_INPUTS="data/processed/medical/nearby_medical_facilities.csv data/processed/osm_nearby/supermarket/nearby_osm_facilities.csv data/processed/osm_nearby/convenience_store/nearby_osm_facilities.csv data/processed/osm_nearby/park_tokyo/nearby_osm_facilities.csv data/processed/osm_nearby/park_kanagawa/nearby_osm_facilities.csv data/processed/osm_nearby/park_saitama/nearby_osm_facilities.csv data/processed/osm_nearby/park_chiba/nearby_osm_facilities.csv" COMMERCIAL_FACILITIES_CSV=data/processed/jcsc/jcsc_sc_open_with_coordinates.csv
```

| column | required | description |
| --- | --- | --- |
| `id` | no | 空の場合はカテゴリ、施設名、緯度経度から自動生成する |
| `category_id` | yes | 標準配信は `commercial_facility`, `cinema`, `museum`, `hot_spring`。収集・比較用途では `hospital`, `supermarket`, `park`, `convenience_store` も扱える |
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

各カテゴリ定義には `sourceLabel`、`sourceUrl`、`licenseLabel`、`coverageArea`、
`generatedAt` を含め、データの出典、配信上の扱い、対象地域、生成日時を確認できるようにする。

入力CSVが存在しない場合は、カテゴリ定義だけを含む未生成JSONを出力する。これにより、フロントエンドはデータ未投入の状態でも同じUIで動作する。

テンプレートを再生成する場合:

```bash
make nearby-facilities-template
```

## 実データ投入時の注意

大量POIをモデル特徴量へ直接入れない。モデルへ使う場合は、距離や半径件数に集計したうえで `docs/surrounding-features.md` の採用基準に沿って比較する。

周辺施設JSONは地図表示用の参考情報であり、価格を保証する情報として表示しない。
