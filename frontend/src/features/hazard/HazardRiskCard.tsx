import type { HazardAssessmentResponse } from "../../types/hazard";

type Props = {
  latitude: number | null;
  longitude: number | null;
  assessment?: HazardAssessmentResponse | null;
};

const HAZARD_PORTAL_URL = "https://disaportal.gsi.go.jp/";
const HAZARD_DATA_SOURCE_URL =
  "https://disaportal.gsi.go.jp/hazardmapportal/hazardmap/copyright/copyright_data.html";
const DEFAULT_DISCLAIMER =
  "本結果は公開データを機械的に整理するための参考情報です。正式な判断には自治体等の最新ハザードマップをご確認ください。";

export function HazardRiskCard({ latitude, longitude, assessment = null }: Props) {
  const hasLocation = latitude !== null && longitude !== null;
  const statusLabel = assessment?.assessment.label ?? (hasLocation ? "地図レイヤーで確認中" : "地点未選択");
  const scoreLabel =
    assessment?.assessment.score !== null && assessment?.assessment.score !== undefined
      ? `${assessment.assessment.score} / 100`
      : "未評価";
  const evaluatedAt = assessment?.metadata.evaluatedAt
    ? new Date(assessment.metadata.evaluatedAt).toLocaleString("ja-JP")
    : "未評価";
  const dataSources = assessment?.metadata.dataSource.join("、") ?? "ハザードマップポータルサイト";

  return (
    <section className="panel hazard-card" aria-label="災害リスク評価" data-testid="hazard-risk-card">
      <div className="panel-title-row">
        <h2>災害リスク評価</h2>
        <span className="inline-status">{statusLabel}</span>
      </div>

      <dl className="hazard-summary-grid">
        <div>
          <dt>総合スコア</dt>
          <dd>{scoreLabel}</dd>
        </div>
        <div>
          <dt>地点</dt>
          <dd>
            {hasLocation
              ? `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`
              : "未選択"}
          </dd>
        </div>
        <div>
          <dt>評価日時</dt>
          <dd>{evaluatedAt}</dd>
        </div>
        <div>
          <dt>データ出典</dt>
          <dd>{dataSources}</dd>
        </div>
      </dl>

      <p className="hazard-note">
        初期MVPでは価格補正には使用せず、洪水レイヤーを地図上に重ねて確認します。地点ごとの数値判定は後続で追加します。
      </p>

      <div className="hazard-links">
        <a href={HAZARD_PORTAL_URL} target="_blank" rel="noreferrer">
          公式ハザードマップを開く
        </a>
        <a href={HAZARD_DATA_SOURCE_URL} target="_blank" rel="noreferrer">
          データ出典を確認
        </a>
      </div>

      <p className="result-disclaimer">{assessment?.metadata.disclaimer ?? DEFAULT_DISCLAIMER}</p>
    </section>
  );
}
