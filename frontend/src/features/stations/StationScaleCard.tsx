import type { StationRecord } from "../../types/assets";

type Props = {
  station?: StationRecord;
  stationName: string;
};

const RANK_LABELS: Record<string, string> = {
  S: "超大規模",
  A: "大規模",
  B: "中規模",
  C: "小中規模",
  D: "小規模",
  unknown: "不明"
};

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 }).format(value);
}

function estimatePassengerCount(station: StationRecord): number | null {
  if (!station.station_passenger_log) {
    return null;
  }
  return Math.max(0, Math.round(Math.expm1(station.station_passenger_log)));
}

export function StationScaleCard({ station, stationName }: Props) {
  const rank = station?.station_rank ?? "unknown";
  const passengerCount = station ? estimatePassengerCount(station) : null;

  return (
    <section className="panel station-scale-card" aria-label="最寄駅の規模" data-testid="station-scale-card">
      <div className="panel-title-row">
        <h2>最寄駅の規模</h2>
        <span className="inline-status">{RANK_LABELS[rank] ?? rank}</span>
      </div>

      {station ? (
        <>
          <dl className="facility-summary-grid">
            <div>
              <dt>駅名</dt>
              <dd>{station.station_name}</dd>
            </div>
            <div>
              <dt>乗降客数</dt>
              <dd>{passengerCount !== null ? `${formatNumber(passengerCount)}人/日` : "不明"}</dd>
            </div>
            <div>
              <dt>路線数</dt>
              <dd>{formatNumber(station.station_line_count ?? 0)}路線</dd>
            </div>
            <div>
              <dt>運営会社数</dt>
              <dd>{formatNumber(station.station_operator_count ?? 0)}社</dd>
            </div>
          </dl>
          <p className="hazard-note">
            駅別乗降客数から作成した参考情報です。価格モデルでは駅カテゴリを軽量化する候補特徴量として比較します。
          </p>
        </>
      ) : (
        <p className="muted">
          {stationName ? `${stationName} の駅規模データは未取得です。` : "駅を選択すると駅規模を表示します。"}
        </p>
      )}
    </section>
  );
}
