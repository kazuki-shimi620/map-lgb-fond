import type { PredictionResult } from "../../types/prediction";

type Props = {
  result: PredictionResult | null;
  isUpdating?: boolean;
};

function formatYen(value: number): string {
  return new Intl.NumberFormat("ja-JP", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0
  }).format(value);
}

export function PredictionResultView({ result, isUpdating = false }: Props) {
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
        {isUpdating ? <span className="inline-status">更新中</span> : null}
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
    </section>
  );
}
