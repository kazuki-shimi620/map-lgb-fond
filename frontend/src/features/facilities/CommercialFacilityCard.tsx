import type {
  CommercialFacilityAreaSummary,
  CommercialFacilitySummary
} from "../../types/assets";

type Props = {
  summary: CommercialFacilitySummary | null;
  prefecture: string;
  municipality: string;
};

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 }).format(value);
}

function formatArea(value: number): string {
  return `${formatNumber(value)}㎡`;
}

function findAreaSummary(
  summary: CommercialFacilitySummary,
  prefecture: string,
  municipality: string
): CommercialFacilityAreaSummary | null {
  const exact = summary.cities[`${prefecture}|${municipality}`];
  if (exact) {
    return exact;
  }

  const cityMatch = Object.values(summary.cities).find(
    (city) =>
      city.prefecture === prefecture &&
      Boolean(city.city) &&
      (municipality.startsWith(city.city ?? "") || (city.city ?? "").startsWith(municipality))
  );
  return cityMatch ?? summary.prefectures[prefecture] ?? null;
}

function formatOpening(opening: CommercialFacilityAreaSummary["recentOpenings"][number]): string {
  const date =
    opening.openYear !== null
      ? `${opening.openYear}年${opening.openMonth !== null ? `${opening.openMonth}月` : ""}`
      : "時期不明";
  return `${opening.name}（${date}）`;
}

export function CommercialFacilityCard({ summary, prefecture, municipality }: Props) {
  const areaSummary = summary ? findAreaSummary(summary, prefecture, municipality) : null;
  const statusLabel = summary ? "参考情報" : "データ未配置";
  const sourceLabel = summary?.sourceLabel ?? "日本ショッピングセンター協会 オープンSC一覧表";
  const coverage = summary?.coverage;

  return (
    <section className="panel commercial-facility-card" aria-label="周辺商業施設" data-testid="commercial-facility-card">
      <div className="panel-title-row">
        <h2>周辺商業施設</h2>
        <span className="inline-status">{statusLabel}</span>
      </div>

      {areaSummary ? (
        <>
          <dl className="facility-summary-grid">
            <div>
              <dt>SC件数</dt>
              <dd>{formatNumber(areaSummary.scCount)}件</dd>
            </div>
            <div>
              <dt>店舗面積合計</dt>
              <dd>{formatArea(areaSummary.storeAreaSumSqm)}</dd>
            </div>
            <div>
              <dt>テナント数合計</dt>
              <dd>{formatNumber(areaSummary.tenantCountSum)}店</dd>
            </div>
            <div>
              <dt>データ更新年</dt>
              <dd>{summary?.latestOpenYear ?? "-"}年</dd>
            </div>
          </dl>
          {coverage ? (
            <p className="facility-coverage-note">
              全国{formatNumber(coverage.facilityCount)}件、地図表示用の信頼座標は
              {formatNumber(coverage.reliableCoordinateCount)}件です。
            </p>
          ) : null}
          {areaSummary.recentOpenings.length > 0 ? (
            <div className="facility-recent-list">
              <h3>直近開業SC</h3>
              <ul>
                {areaSummary.recentOpenings.map((opening) => (
                  <li key={`${opening.name}-${opening.openYear}-${opening.openMonth}`}>
                    {formatOpening(opening)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="hazard-note">
            価格モデルへの採用とは分けた参考情報です。地図では信頼座標がある商業施設だけを表示します。
          </p>
          <p className="result-disclaimer">出典: {sourceLabel}</p>
        </>
      ) : (
        <p className="muted">
          商業施設の配信用データが未生成です。学習側で `make facilities` を実行すると表示できます。
        </p>
      )}
    </section>
  );
}
