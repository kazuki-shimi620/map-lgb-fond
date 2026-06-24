import { useState } from "react";
import type { PredictionResult } from "../../types/prediction";

type Props = {
  result: PredictionResult | null;
  summary?: {
    station: string;
    stationDistance: number;
    modelRegion: string;
    latestTrainingYear: number | null;
    trainStartYear: number | null;
    evaluationMae: number | null;
    evaluationRmse: number | null;
    trainCount: number | null;
    generatedAt: string | null;
    featureImportance: Array<{
      feature: string;
      importance: number;
    }>;
  };
};

const FEATURE_LABELS: Record<string, string> = {
  area: "面積",
  age: "築年数",
  station_distance: "駅徒歩",
  prefecture: "都道府県",
  municipality: "市区町村",
  station: "駅",
  room_layout: "間取り",
  building_type: "建物構造",
  transaction_year: "取引年"
};

function formatExactYen(value: number): string {
  return `${new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 }).format(value)}円`;
}

function formatManYen(value: number): string {
  return `${new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 }).format(Math.round(value / 10000))}万円`;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(date);
}

export function PredictionResultView({ result, summary }: Props) {
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  if (!result) {
    return (
      <section className="panel result-panel">
        <h2>予測結果</h2>
        <p className="muted">条件を入力して予測してください。</p>
      </section>
    );
  }

  return (
    <section className="panel result-panel">
      <div className="panel-title-row">
        <h2>予測結果</h2>
      </div>
      <dl className="result-grid">
        <div>
          <dt>予測価格</dt>
          <dd>
            <span className="price-main">{formatManYen(result.predictedPrice)}</span>
            <span className="price-sub">({formatExactYen(result.predictedPrice)})</span>
          </dd>
        </div>
        <div>
          <dt>平米単価</dt>
          <dd>
            <span className="price-main">{formatManYen(result.pricePerSquareMeter)}</span>
            <span className="price-sub">({formatExactYen(result.pricePerSquareMeter)} / m2)</span>
          </dd>
        </div>
        <div>
          <dt>信頼区間</dt>
          <dd>
            {formatManYen(result.lowerPrice)} - {formatManYen(result.upperPrice)}
          </dd>
        </div>
      </dl>
      {summary ? (
        <>
          <button
            type="button"
            className="detail-toggle"
            aria-expanded={isDetailOpen}
            onClick={() => setIsDetailOpen((current) => !current)}
          >
            {isDetailOpen ? "詳細を閉じる" : "条件・モデル詳細を表示"}
          </button>
          {isDetailOpen ? (
            <div className="result-detail">
              <section className="detail-section">
                <h3>条件</h3>
                <dl className="detail-grid">
                  <div>
                    <dt>最寄駅</dt>
                    <dd>{summary.station}</dd>
                  </div>
                  <div>
                    <dt>駅徒歩</dt>
                    <dd>{summary.stationDistance}分</dd>
                  </div>
                  <div>
                    <dt>対応地域</dt>
                    <dd>{summary.modelRegion}</dd>
                  </div>
                </dl>
              </section>
              <section className="detail-section">
                <h3>モデル評価</h3>
                <dl className="detail-grid">
                  <div className="detail-wide">
                    <dt>学習データ</dt>
                    <dd>
                      {summary.modelRegion}中古マンション取引データ
                      <span className="summary-note">
                        ({summary.trainStartYear ?? "-"}-{summary.latestTrainingYear ?? "-"})
                      </span>
                    </dd>
                  </div>
                  <div>
                    <dt>最終学習日</dt>
                    <dd>{formatDate(summary.generatedAt)}</dd>
                  </div>
                  <div>
                    <dt>MAE</dt>
                    <dd>{summary.evaluationMae !== null ? formatManYen(summary.evaluationMae) : "-"}</dd>
                  </div>
                  <div>
                    <dt>RMSE</dt>
                    <dd>{summary.evaluationRmse !== null ? formatManYen(summary.evaluationRmse) : "-"}</dd>
                  </div>
                  <div>
                    <dt>学習件数</dt>
                    <dd>{summary.trainCount !== null ? `${summary.trainCount.toLocaleString("ja-JP")}件` : "-"}</dd>
                  </div>
                </dl>
              </section>
              {summary.featureImportance.length > 0 ? (
                <section className="detail-section importance-panel" aria-label="特徴量重要度">
                  <h3>特徴量重要度</h3>
                  <ol>
                    {summary.featureImportance.slice(0, 5).map((item) => (
                      <li key={item.feature}>
                        <span>{FEATURE_LABELS[item.feature] ?? item.feature}</span>
                        <meter min="0" max={summary.featureImportance[0].importance || 1} value={item.importance} />
                      </li>
                    ))}
                  </ol>
                </section>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
      <p className="result-disclaimer">
        予測価格は公開取引データに基づく参考値です。実際の査定額や成約価格を保証するものではありません。
      </p>
    </section>
  );
}
