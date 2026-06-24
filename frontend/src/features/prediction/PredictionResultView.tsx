import type { PredictionResult } from "../../types/prediction";

type Props = {
  result: PredictionResult | null;
  summary?: {
    station: string;
    stationDistance: number;
    modelRegion: string;
    latestTrainingYear: number | null;
  };
};

function formatYen(value: number): string {
  return new Intl.NumberFormat("ja-JP", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0
  }).format(value);
}

export function PredictionResultView({ result, summary }: Props) {
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
          <dd>{formatYen(result.predictedPrice)}</dd>
        </div>
        <div>
          <dt>平米単価</dt>
          <dd>{formatYen(result.pricePerSquareMeter)} / m2</dd>
        </div>
        <div>
          <dt>信頼区間</dt>
          <dd>
            {formatYen(result.lowerPrice)} - {formatYen(result.upperPrice)}
          </dd>
        </div>
      </dl>
      {summary ? (
        <dl className="result-summary">
          <div>
            <dt>最寄駅</dt>
            <dd>{summary.station}</dd>
          </div>
          <div>
            <dt>駅徒歩</dt>
            <dd>{summary.stationDistance}分</dd>
          </div>
          <div>
            <dt>利用モデル</dt>
            <dd>{summary.modelRegion}</dd>
          </div>
          <div>
            <dt>学習最終年</dt>
            <dd>{summary.latestTrainingYear ?? "-"}</dd>
          </div>
        </dl>
      ) : null}
      <p className="result-disclaimer">
        予測価格は公開取引データに基づく参考値です。実際の査定額や成約価格を保証するものではありません。
      </p>
    </section>
  );
}
