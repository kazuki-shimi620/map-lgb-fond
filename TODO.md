# TODO

## 作業方針

P0/P1を優先する。ONNX再生成、`frontend/public/models`、`frontend/public/metadata`、`frontend/public/stations` の成果物反映、`make train-all PUBLISH_POLICY=latest` はP2として後でまとめて実施する。

有料API、有料契約前提、料金不明、またはキャッシュ・再配布条件が曖昧な外部サービスは使わず、P3または調査保留へ回す。無料の公式APIやオープンデータだけを優先し、APIキーが必要な無料APIもブラウザから直接呼ばず学習側の取得処理に閉じ込める。

コミットはTODOの細かい単位で行う。完了済みタスクの詳細はgit logと `docs/` に残し、TODOには原則として未完了・判断待ちの作業だけを置く。

## P0/P1 次に進める作業

### モデル採用判断

* [x] 新規外部特徴量を本番モデルへ入れる前に、各 `compare-*-features` のMAE/RMSE/MAPE、ONNXサイズ、辞書サイズ、Feature Importance、データマッチ率を一覧化する
* [x] 外部特徴量ごとに「モデル採用」「参考表示のみ」「保留/不採用」を決める採用表を作る
* [x] 本番モデル候補はまず `地価`、`用途地域`、`人口統計` を優先し、教育施設・犯罪統計は初期は参考表示優先で扱う
* [ ] 採用候補だけを `configs/*.yaml` の `features` / `categorical_features` に追加し、モデル再生成、metadata更新、TypeScript推論契約テスト、フロントbuildをまとめて実施する
  * [x] 2026-07-15に効果差のなかった `has_station_passenger_data` を首都圏4県configから外し、ONNX/metadata再生成、feature orderチェック、frontend buildを実行する
  * [x] 2026-07-15に首都圏4県configを `train_start_year: 2015` へ切り替え、ONNX/metadata再生成、feature orderチェック、frontend buildを実行する
  * [x] 2026-07-15に地価特徴量を首都圏4県configへ追加し、ONNX/metadata再生成、feature orderチェック、frontend buildを実行する。全体MAE -5,564円、RMSE -10,937円、ONNX合計 -3.59MB
  * [x] 2026-07-15に座標付き検証用Parquetで地価・用途地域の同時投入バックテストを追加実行し、stationありMAE -53,516円、stationなしMAE -252,236円を確認する
  * [x] 用途地域特徴量を本番configへ入れる前に、ブラウザ推論で同じ用途地域特徴量を再現する静的データ配信とTypeScript実装を追加する
  * [x] 2026-07-15に首都圏4県configへ用途地域特徴量を追加し、座標付きParquetでONNX/metadata再生成、feature orderチェック、frontend buildを実行する。直前比MAEは東京 -194,607円、神奈川 -113,077円、埼玉 -19,004円、千葉 -47,948円
* [x] `featureOrder` に新特徴量を追加する場合は、TypeScript側のエンコード対応、カテゴリ辞書、default値の必要性を同じPR/commitで確認する

### 実データ取得・比較

* [ ] `make collect-land-prices` で首都圏4県の地価ポイントCSVを生成する
  * [x] `make collect-land-prices-dry-run` と `make collect-land-prices-tile` を追加し、1タイル疎通で26ポイント・5自治体集計を確認する
  * [x] 2026-07-15に `LAND_PRICE_YEARS=2025` の1タイル実取得とカバレッジ集計、地価特徴量バックテストを再実行する
  * [x] 2026-07-15に `LAND_PRICE_YEARS=2025 LAND_PRICE_ZOOM=13` の段階取得を実行し、12,235ポイント・630自治体集計・マッチ率9.25%を確認する
  * [x] 2026-07-15にカバレッジレポートへ取引データの座標件数を追加し、現Parquetは `lat` / `lon` 未保持のため近傍地価特徴量が0になることを確認する
  * [x] 2026-07-15に `LAND_PRICE_YEARS=2024,2025 LAND_PRICE_ZOOM=13` の段階取得を実行し、24,486ポイント・1,260自治体集計・マッチ率17.96%を確認する
  * [x] 地価ポイントの近傍特徴量を比較する前に、取引データへ緯度経度を付与する方針を決める
  * [x] 将来の座標付与に備え、前処理で公式CSVの `地区名` と任意の `lat` / `lon` を保持する
  * [x] 取引データへ緯度経度を付与する代表点データソースを選定し、座標精度レポートを追加する
  * [x] Geolonia住所データを取得・正規化し、277,189町丁目代表点・CSV 25.3MB・現行Parquet市区町村代表点マッチ率99.74%を確認する
  * [x] `district_name` を保持する形で首都圏4県を再前処理し、町丁目完全一致19.33%、地区prefix代表点80.25%、市区町村代表点0.17%を確認する
  * [x] 町丁目/地区prefix代表点を付与した検証用Parquetを生成し、市区町村代表点フォールバックなしで682,846件・99.57%に座標を付与する
  * [x] 座標付き検証用Parquetで用途地域・地価近傍・教育施設の空間特徴量をサンプルdry-run比較する。200件サンプルで地価近傍マッチ19.50%、用途地域zoningマッチ97.50%、教育施設は実データ未取得のため0.00%
  * [x] 地価近傍特徴量をBallTreeで高速化し、座標付き検証用Parquetの全件カバレッジとバックテストを再実行する。地価マッチ18.04%、stationありMAE -40,282円、stationなしMAE -116,573円
  * [x] 用途地域判定をグリッド索引とユニーク座標単位に高速化し、座標付き検証用Parquetで全件カバレッジを再実行する。zoningマッチ656,910件・95.79%
  * [x] 用途地域特徴量のバックテスト導線を追加し、座標付き検証用Parquetで再実行する。stationありMAE -13,846円、stationなしMAE -163,364円
  * [ ] 首都圏4県・2024/2025年・z=14は16,960リクエストになるため、ネットワーク許可済み環境で長時間ジョブとして実行する
* [x] 公示地価/基準地価を取得し、地価水準と地価変化率を比較する
  * [x] `make summarize-land-price-coverage` を追加し、取得後に地価水準・変化率・マッチ率・配布サイズを確認できるようにする
  * [x] 2026-07-15にz=13・2025年データで `make compare-land-price-features` を再実行し、現特徴量ではベースライン同等と確認する
  * [x] 2026-07-15にz=13・2024/2025年データで `make compare-land-price-features` を再実行し、stationありでMAE -17,671円、stationなしでMAE -5,099円を確認する
  * [x] 2026-07-15に座標付き検証用Parquetで近傍地価を含む `compare_land_price_features.py` を再実行し、stationありでMAE -40,282円、stationなしでMAE -116,573円を確認する
  * [x] 地価特徴量を本番configへ入れる前に、ブラウザ推論で同じ市区町村地価特徴量を再現する静的データ配信とTypeScript実装を追加する
  * [x] 地価特徴量を首都圏4県configへ追加し、モデル再生成、metadata更新、TypeScript推論契約テスト、フロントbuildを実施する
* [ ] 人口・世帯数・人口密度・年齢構成を自治体単位で比較する
  * [x] 自治体人口統計CSVの入力スキーマ、テンプレート、生成ターゲットを追加する
  * [x] `make summarize-population-coverage` を追加し、取得後に人口・世帯・人口密度・年齢構成・マッチ率・配布サイズを確認できるようにする
* [x] 用途地域データを取得し、用途地域、建ぺい率、容積率、区域区分のマッチ率と配布サイズを確認する
  * [x] `make collect-urban-planning-dry-run` を追加し、首都圏4県・z=13・3 APIで6,480リクエストになることを確認する
  * [x] `make collect-urban-planning-tile` を追加し、1タイル疎通できる導線を用意する
  * [x] `make summarize-urban-planning-coverage` を追加し、取得後にマッチ率と配布サイズを確認できるようにする
  * [x] 2026-07-15に `XKT002` の1タイル実取得とカバレッジ集計を再実行する
  * [x] 2026-07-15に `XKT002` を首都圏4県z=13で広域取得し、38,110エリア・CSV 55.2MBを確認する
  * [x] 用途地域カバレッジレポートへ取引データの座標件数を追加し、現Parquetは `lat` / `lon` 未保持のためマッチ率0.00%になることを確認する
  * [x] 用途地域特徴量を比較する前に、取引データへ緯度経度を付与する方針を決める
  * [x] 取引データへ緯度経度を付与した検証用Parquetで、200件サンプルの用途地域zoningマッチ97.50%を確認する
  * [x] 取引データへ緯度経度を付与した後に、用途地域特徴量の全件カバレッジを再実行し、zoningマッチ656,910件・95.79%を確認する
  * [x] 取引データへ緯度経度を付与した後に、用途地域特徴量のバックテストを再実行し、stationありMAE -13,846円、stationなしMAE -163,364円を確認する
  * [x] 地価・用途地域の同時投入バックテスト導線を追加し、座標付き検証用Parquetで再実行する。stationありMAE -53,516円、stationなしMAE -252,236円
  * [x] `make urban-planning` を追加し、用途地域ポリゴンを `frontend/public/urban-planning/urban_planning_areas.json` として配信し、TypeScript側でピン座標から同じ特徴量を再現する
* [x] 教育施設データを取得し、小学校/中学校距離、保育園/幼稚園件数のマッチ率と表示価値を確認する
  * [x] `make collect-education-facilities-dry-run` を追加し、首都圏4県・z=13・4 APIで8,640リクエストになることを確認する
  * [x] `make collect-education-facilities-tile` を追加し、1タイル疎通できる導線を用意する
  * [x] `make summarize-education-coverage` を追加し、取得後にマッチ率と配布サイズを確認できるようにする
  * [x] 2026-07-15に `XKT005` の1タイル実取得とカバレッジ集計を再実行する
  * [x] 2026-07-15に `XKT006,XKT007` を首都圏4県z=13で取得し、23,941施設・CSV 6.2MBを確認する
  * [x] 教育施設距離計算をBallTreeとユニーク座標単位に高速化し、座標付き検証用Parquetでマッチ率99.57%を確認する
* [x] 病院、スーパー、商業施設、公園、コンビニの周辺施設データを静的配信用JSONへ生成する
* [x] 病院、スーパー、商業施設、公園、コンビニの実データCSVを作成または取得する
  * [x] 周辺施設CSVの入力スキーマ、テンプレート、exporterテストを追加する
  * [x] JCSC商業施設CSVへGeolonia町丁目代表点で代表座標を付与し、429件中144件を `commercial_facility` マーカーとして周辺施設JSONへ出力する
  * [x] JCSCの全国商業施設一覧PDFを追加ソースとして取り込み、既存JCSC CSVの不足分を補完する
    * [x] 対象PDF: `https://www.jcsc.or.jp/wpjcsc/wp-content/uploads/2026/05/35212d5b060e16d7f8db21681d51d151.pdf`
    * [x] 2026-07-15にPDFを手動ダウンロード済み。生PDFはGit管理せず、作業時は `training/data/raw/jcsc_pdf/` などGit管理外のraw領域へ配置して解析する
    * [x] `pdfplumber`、`pypdf`、`PyMuPDF`、Poppler系CLIのいずれかを使えるようにし、PDFテキスト抽出と表抽出の再現手順をMakefileまたはcollectorへ追加する
      * 2026-07-15に `pdfplumber` + `pypdfium2` + macOS Vision OCR (`ocrmac`) を使う `make collect-sc-pdf` を追加した。OCR依存は `training` の `ocr` optional extra に分離する
    * [x] PDFからSC名、オープン日、店舗面積/施設面積など、表に含まれる列を抽出する。PDF表解析は時間がかかる前提で、まずサンプル数十件を手動確認する
      * 2026-07-15に全23ページを解析し、2,804件を `training/data/processed/jcsc_pdf/jcsc_sc_pdf_facilities.csv` に抽出した。出力はGit管理外のprocessedデータとして扱う
      * 市区町村から都道府県を補正し、47都道府県に復元した。補正行1,257件、 municipality欠損324件、面積欠損4件、オープン年月欠損4件はレビュー対象
      * 2026-07-16にページごとの抽出施設数とOCR結果の「月」文字数を `training/data/processed/jcsc_pdf/jcsc_sc_pdf_page_month_audit.csv` へ出力した。全体は抽出2,804件に対して「月」2,991件で、4/13/16ページは一致、1/2/3/5/6/7/8/9/10/11/12/14/15/17/18/19/20/21/22/23ページは抽出行数が少ない。特に10ページ -53件、19ページ -31件、20ページ -26件を優先して目視確認する
      * 2026-07-16に「年」文字数も監査へ追加し、欠落が多い10/19/20ページから再確認した。面積だけOCRで落ちる行を補助抽出するようにして、抽出数は2,928件、不足候補は2,748件へ増加した。再監査では「年」基準の最大差分は12ページ -7件、2/18ページ -6件、5/10/11ページ -5件まで縮小した
      * 2026-07-16に差分3件以上のページだけを追加精査し、左右カラムを別々に行グルーピングするよう修正した。抽出数は2,991件、不足候補は2,797件になり、ページ別の抽出数と「月」文字数は全体一致、差分3件以上のページは0件になった。施設名が空の81件は `training/data/processed/jcsc_pdf/jcsc_sc_pdf_empty_name_review.csv` へ切り出した
      * 2026-07-16に空名レビューCSVへ `facility_name` 列を追加し、16/17/22ページの66件をPDF目視で補完して `commercial_facility_row_corrections.csv` へ反映した。残る空名レビューは14ページの6件
      * 2026-07-16にPDF再監査を行い、抽出2,991件と「月」文字数2,991件が全体一致することを再確認した。row correction適用後の空名残件は14ページのみ
      * [x] 2026-07-16に14ページを除く差分3件未満の小差分ページも `training/data/processed/jcsc_pdf/jcsc_sc_pdf_small_mismatch_empty_review.csv` へ切り出した。対象は1/4/5/10/12/13/20/23ページの17行で、折り返し候補11行、面積欠け候補2行、開業月OCR欠け4行
      * [x] 2026-07-16に小差分レビュー17件を `commercial_facility_row_corrections.csv` へ反映した。開業月不明の稲毛オーツパーク、下田とうきゅう、フジグラン北宇和島は1月として補完し、いせさきガーデンズは手動入力の12月を反映した
      * [x] 2026-07-16に反映済み行をレビューCSVから除外した。`jcsc_sc_pdf_small_mismatch_empty_review.csv` はヘッダーのみ、`jcsc_sc_pdf_empty_name_review.csv` は14ページ左カラムの日進市4件のみ残件
      * [x] 2026-07-16にユーザー補完済みの14ページ左カラム4件を `commercial_facility_row_corrections.csv` へ反映した。`jcsc_sc_pdf_empty_name_review.csv` はヘッダーのみで未完了0件
    * [x] 既存の `training/data/processed/jcsc/jcsc_sc_open.csv` とSC名、開業日、都道府県、市区町村、面積で突合し、既存データにない施設・既存より情報が詳しい施設を差分CSVへ分ける
      * 2026-07-15時点ではSC名正規化+都道府県の一次突合で、2,634件を `training/data/processed/jcsc_pdf/jcsc_sc_pdf_new_candidates.csv` に不足候補として出力した。開業日・面積を含む厳密突合は次のレビュー工程で精査する
    * [x] PDF由来データは住所や緯度経度が不足する可能性が高いため、SC名、都道府県、施設名表記ゆれを使って段階的に所在地を補完する
      * [x] 2026-07-15にPDF不足候補2,634件へ座標補完導線を追加し、2,627件に市区町村代表点の低信頼仮座標を付与した。確定座標ではないため、地図マーカー公開前にGoogle Map等で確認する
      * [x] 郡名省略、`ケ/ヶ` 表記差、同一都道府県内の高類似OCR誤読、手動自治体alias、行政区alias、施設名aliasを使って、初期2,099件から528件ぶん仮座標補完を改善した
      * [x] Google Map検索用URL付きの `coordinate_review_queue.csv` を生成し、`coordinate_missing` 5件、`ocr_name_review` 114件、`low_confidence_municipality_representative` 2,515件に分類した
      * [x] 2026-07-16に目視確認済み住所7件を `commercial_facility_row_corrections.csv` へ反映し、PDF不足候補2,634件すべてに座標を付与した。住所確認済み7件は町丁目代表点の中信頼、残り2,627件は市区町村代表点の低信頼
      * [x] 2026-07-16のPDF再抽出後に座標補完を再実行し、不足候補2,748件中2,724件に座標を付与した。内訳は市区町村代表点2,717件、住所一致7件、未補完24件
      * [x] 2026-07-16の差分3件以上ページの再抽出後に座標補完を再実行し、不足候補2,797件中2,768件に座標を付与した。内訳は市区町村代表点2,761件、住所一致7件、未補完29件
      * [x] 16/17/22ページの空名補完をrow correctionとして適用し、補完後CSVで店名・都道府県・市区町村が反映されることを確認した
      * [x] 店名補完済みで住所未確認の66件を `training/data/processed/jcsc_pdf/jcsc_sc_pdf_address_review_queue.csv` に切り出し、公式住所確認用の検索URLを付与した。公式ページで確認できた阪急西宮ガーデンズ、OPSIA misumi、マルヤガーデンズの3件は住所をrow correctionへ反映した
      * [x] 2026-07-16に住所未確認63件をOSM/Nominatimで照合し、施設名・自治体が合う28件を `commercial_facility_manual_coordinates.csv` へ中信頼候補として反映した。出力CSVでは住所付き38件、manual OSM 28件、住所一致10件になった
      * [x] 2026-07-16にOSM/Nominatimの表記ゆれ再検索を行い、追加12件を中信頼/低信頼候補として反映した。出力CSVでは住所付き50件、manual OSM 40件、住所一致10件になった
      * [x] 2026-07-16に公式アクセスページで高槻阪急スクエア、Corowa甲子園の住所を確認し、出力CSVでは住所付き52件になった
      * [x] 2026-07-16にGoogle Map確認候補として20件の詳細住所を `commercial_facility_row_corrections.csv` へ反映し、出力CSVでは住所付き72件になった
      * [x] 2026-07-16にユーザー確認済み住所として伊丹ショッピングデパート `兵庫県伊丹市中央1丁目1-1` を反映し、住所未解決キューはヘッダーのみになった。出力CSVでは住所付き73件になった
      * [x] 2026-07-16に旧JCSC座標付きCSVとPDF由来座標付きCSVを同時に扱えるよう、商業施設サマリー、周辺施設マーカー、商業施設特徴量比較を複数CSV入力へ対応した
    * [ ] 位置情報は一括自動化を急がず、SC名で公式サイト・自治体/商業施設ページ・地図検索を確認し、出典URL、確認日、信頼度を記録する手動補完CSVを用意する
      * [x] `training/data/manual/facilities/commercial_facility_manual_coordinates.csv` を追加し、Google Map検索などで確認した住所・緯度経度・出典URL・確認日・信頼度を記録できるようにした
      * [x] `training/data/manual/facilities/commercial_facility_municipality_aliases.csv` を追加し、PDF OCR由来の明らかな自治体誤読を追跡可能な手動aliasとして補正できるようにした
      * [x] `training/data/manual/facilities/commercial_facility_row_corrections.csv` を追加し、ページ・カラム・面積・開業年月で特定できるOCR空欄行を目視確認住所で補正できるようにした
      * [ ] `coordinate_missing` と `ocr_name_review` を優先してGoogle Map検索で確認し、確定したものを手動補完CSVへ追記する
      * [ ] KIPPY MALL、イオン三好ショッピングセンターなど、PDF上には存在するが現CSVに独立行として抽出されていない施設を追加行として補完する
    * [x] 住所または緯度経度を補完できた施設だけ `commercial_facility` マーカーへ追加し、補完できない施設はモデル集計用の市区町村/都道府県単位データに留める
      * [x] 市区町村代表点の低信頼仮座標はマーカー公開に使わず、manual補完または住所一致で信頼度medium以上になった施設だけを周辺施設JSONへ統合する
      * [x] 2026-07-16に `nearby_facilities.json` を再生成し、商業施設マーカーは旧JCSC住所点176件、PDF由来手動/住所点35件の合計211件になった。低信頼の市区町村代表点2,695件はマーカーから除外した
    * [x] PDF由来データと既存JCSCデータを統合した後、商業施設の対象エリア、件数、座標付与率、面積欠損率をmetadataとドキュメントへ記録する
      * [x] 2026-07-16に `commercial_facilities.json` の `coverage` へ全国3,197件、座標あり2,912件、信頼座標211件、面積欠損75件、座標付与率91.09%、信頼座標率6.60%、面積欠損率2.35%を記録した
  * [x] 不動産情報ライブラリ `XKT010` 医療機関APIから病院マーカー用CSVを生成するcollector、dry-run、1タイル疎通ターゲットを追加する
  * [x] 2026-07-15に `XKT010` 医療機関APIを1タイル実取得し、病院210件を周辺施設JSONへ反映する
  * [x] `make collect-medical-facilities` で首都圏4県の医療機関を長時間ジョブとして取得し、59,062件の病院マーカーを全域反映する
  * [x] OpenStreetMap/Overpass APIからスーパー6,345件、コンビニ17,190件、公園27,231件を取得し、周辺施設JSONへ反映する
  * [x] 周辺施設カテゴリごとの対象エリアを明記する。商業施設は全国元データ、病院は首都圏4県、スーパー/コンビニは首都圏bbox、公園は首都圏4県分割取得
  * [ ] 周辺施設を全国対応する場合は、病院・スーパー・コンビニ・公園を都道府県または地域ブロック単位で取得し、metadataへカテゴリ別対象エリアを出力する
  * [x] OpenStreetMap ODbLの表示上の帰属表記と、地図レイヤーでの大量マーカー描画負荷を確認する
    * [x] 周辺施設パネルにOpenStreetMap contributors (ODbL)への帰属リンクを表示し、表示範囲内・中心近傍の最大1,200件だけを描画する
  * [ ] 公園は大型公園特徴量用に面積またはway/relation面積を別途集計する
    * [x] OSM公園取得に `--include-geometry` と `park_areas.csv` 出力を追加し、geometry面積またはbounds概算面積を保存できるようにする
    * [x] 2026-07-15に東京サンプルbboxで実取得し、827公園マーカー・799面積行を生成できることを確認する
    * [x] `--split-size-degrees` と `--continue-on-error` を追加し、小bbox 4分割で3セル成功・1セル429をmetadataへ記録しながら575公園マーカー・549面積行を結合できることを確認する
    * [x] 2026-07-15に東京全域0.1度グリッドを実行し、40セル中12セル成功・28セル失敗で2,801公園マーカー・2,717面積行を生成するところまで確認する
    * [ ] 東京全域 `out geom` はOverpass 504のため、小bbox分割で首都圏全域の `park_areas.csv` を生成する
* [x] 犯罪統計は無料公開CSV/Excelがある自治体だけでfixture検証し、全国統一のモデル特徴量としては急がない

### 参考表示・UI

* [x] 商業施設に緯度経度を付与できるようになったら、最寄SC距離と地図マーカー表示を追加する
  * [x] JCSC商業施設CSVに緯度経度がある場合、周辺施設JSONへ `commercial_facility` マーカーとして取り込む
  * [x] JCSC商業施設CSVに町丁目代表座標を付与し、144件の地図マーカー表示を生成する
  * [x] 2026-07-16にPDF由来データを追加し、信頼座標medium以上の商業施設211件を地図マーカーへ反映した
  * [x] JCSC商業施設CSVに緯度経度がある場合、取引年以前の最寄SC距離・周辺件数・面積/テナント集計を特徴量化する
  * [x] 2026-07-15に商業施設バックテストを再実行し、緯度経度未付与CSVでは距離系特徴量が基準同等になることを確認する
* [x] ハザード表示と同じ地図レイヤー操作で、病院、スーパー、商業施設、公園、コンビニなどの周辺施設マーカーを表示できるようにする
* [x] 教育施設、用途地域、人口統計、犯罪統計を参考情報カードとして表示する場合の文言、出典表示、年度表示を設計する
* [x] 犯罪・治安指標は星評価にせず、人口1000人あたり刑法犯認知件数、件数、出典、年度、集計単位だけを表示する

## P2 モデル更新時にまとめて実施

* [ ] 商業施設特徴量をハザード特徴量と組み合わせる比較時に再評価する
  * [x] 2026-07-15に `make compare-external-features` を再実行し、ハザードCSV未作成時は候補スキップ、商業施設+駅規模は駅規模単独より弱いことを確認する
  * [x] 2026-07-16にPDF由来データ統合後の `make compare-commercial-features` を再実行し、SC件数3,226件で `city_counts_scale_prefecture_trend` がbaseline比MAE -4,541円の小改善、距離系は基準同等であることを確認した
* [ ] ハザード特徴量は商業施設特徴量の比較後に追加し、精度改善よりもリスク説明力・表示価値も含めて採用判断する
  * [ ] `training/data/processed/hazards/hazard_features.csv` を作成してからハザード候補を再比較する
* [x] 2015年開始はバックテストでは良いが2025年holdoutで微悪化したため、採用前に複数holdout年で再検証する
  * [x] 2026-07-15に `make compare-train-start-years` を実行し、2023/2024/2025 holdoutすべてで2015開始が2005開始より良いことを確認する
  * [x] 2026-07-15に2015開始モデルを再生成し、更新前比で全体MAE -82円、ONNX合計 -8.71MB を確認する
* [ ] 首都圏以外の地方モデルにも駅規模特徴量を入れる場合、全国範囲の駅別乗降客数を取得して再評価する
  * [x] `make collect-station-passengers-national-dry-run` を追加し、全国範囲・z=11で18,477リクエストになることを確認する
  * [x] 2026-07-15に首都圏の駅乗降客数特徴量バックテストを再実行し、2015開始・stationありでMAE 5,423,317円を確認する
* [ ] 将来人口変化率を比較候補にする場合は、不動産情報ライブラリ `XKT013` との接続後にFeatureProviderへ追加する

## P3 将来的な改善

* [ ] データ量を増やす、県と年度
* [ ] 大型公園特徴量の取得・比較
* [ ] 病院特徴量の取得・比較
* [ ] 大学特徴量の取得・比較
* [ ] 再開発エリア特徴量の手動マスタ検討

## 理想フロー

```text
ローカルまたは手動workflowでデータ取得
↓
前処理
↓
比較レポートでモデル採用/参考表示/不採用を判断
↓
採用候補だけconfigsへ追加
↓
学習
↓
ONNX/metadata出力
↓
成果物更新PR
↓
mainマージ後にGitHub Pagesデプロイ
```
