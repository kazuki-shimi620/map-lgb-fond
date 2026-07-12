import { Legend, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PriceHistoryPoint } from "../../types/assets";

const ARCHIVE_END_YEAR = 2019;
const RECENT_HISTORY_START_YEAR = 2020;

type Props = {
  points: PriceHistoryPoint[];
  hasHistory: boolean;
  isArchiveLoaded: boolean;
  isArchiveLoading: boolean;
  onLoadArchive: () => void;
  onCloseArchive: () => void;
};

export function PriceHistoryChart({
  points,
  hasHistory,
  isArchiveLoaded,
  isArchiveLoading,
  onLoadArchive,
  onCloseArchive
}: Props) {
  const chartData = buildChartData(points);
  const earliestYear = chartData.at(0)?.year ?? RECENT_HISTORY_START_YEAR;
  const xAxisStart = Math.min(earliestYear, RECENT_HISTORY_START_YEAR);
  const estimatedDots = chartData.filter(
    (point) => point.estimated_price !== null && point.actual_price === null
  );
  const forecastDots = chartData.filter(
    (point) => point.forecast_price !== null && !point.forecast_anchor
  );

  return (
    <section className="panel chart-panel" data-testid="price-history-chart">
      <h2>価格推移</h2>
      {points.length === 0 ? (
        <p className="muted">価格推移データがありません。</p>
      ) : (
        <div className="chart-scroll">
          <div className="chart-canvas">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData} margin={{ top: 12, right: 12, bottom: 8, left: 4 }}>
                <XAxis
                  dataKey="year"
                  type="number"
                  domain={[xAxisStart, "dataMax"]}
                  allowDecimals={false}
                  interval="preserveStartEnd"
                  tickMargin={8}
                />
                <YAxis
                  width={64}
                  tickMargin={8}
                  tickFormatter={(value) => `${Math.round(Number(value) / 10000)}万`}
                />
                <Tooltip
                  formatter={(value, name, item) => {
                    if (name === "入力条件の予測" && item.payload?.forecast_anchor) {
                      return [null, null];
                    }
                    if (
                      name === "周辺実績・モデルによる推計" &&
                      item.payload?.actual_price !== null
                    ) {
                      return [null, null];
                    }
                    const count = item.payload?.actual_count;
                    const estimateCount = item.payload?.estimated_count;
                    const countLabel =
                      name === "対象駅の類似実績" && count
                        ? `（${count}件）`
                        : name === "周辺実績・モデルによる推計" && estimateCount
                          ? `（周辺${estimateCount}件）`
                          : "";
                    return [`${Math.round(Number(value) / 10000)}万円${countLabel}`, name];
                  }}
                />
                <Legend />
                <Line
                  name="対象駅の類似実績"
                  type="monotone"
                  dataKey="actual_price"
                  stroke="#1d4ed8"
                  strokeWidth={2}
                  dot
                  connectNulls
                />
                <Line
                  name="周辺実績・モデルによる推計"
                  type="monotone"
                  dataKey="estimated_price"
                  stroke="#0f766e"
                  strokeWidth={2}
                  strokeDasharray="3 4"
                  dot={false}
                  connectNulls
                />
                <Line
                  name="入力条件の予測"
                  type="monotone"
                  dataKey="forecast_price"
                  stroke="#d97706"
                  strokeWidth={2}
                  strokeDasharray="6 5"
                  dot={false}
                  connectNulls
                />
                {estimatedDots.map((point) => (
                  <ReferenceDot
                    key={`estimated-dot-${point.year}`}
                    x={point.year}
                    y={point.estimated_price ?? 0}
                    r={2.5}
                    fill="#fff"
                    stroke="#0f766e"
                    strokeWidth={2}
                    ifOverflow="discard"
                  />
                ))}
                {forecastDots.map((point) => (
                  <ReferenceDot
                    key={`forecast-dot-${point.year}`}
                    x={point.year}
                    y={point.forecast_price ?? 0}
                    r={3}
                    fill="#fff"
                    stroke="#d97706"
                    strokeWidth={2}
                    ifOverflow="discard"
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      {hasHistory ? (
        <button
          className="history-archive-button"
          type="button"
          onClick={isArchiveLoaded ? onCloseArchive : onLoadArchive}
          disabled={isArchiveLoading}
        >
          {isArchiveLoading
            ? "過去の実績を読み込んでいます"
            : isArchiveLoaded
              ? `${RECENT_HISTORY_START_YEAR}年以降の表示に戻す`
              : `${ARCHIVE_END_YEAR}年以前の実績を表示`}
        </button>
      ) : null}
    </section>
  );
}

function buildChartData(points: PriceHistoryPoint[]) {
  const sortedPoints = [...points].sort((a, b) => a.year - b.year);
  const rows = new Map<
    number,
    {
      year: number;
      actual_price: number | null;
      estimated_price: number | null;
      forecast_price: number | null;
      actual_count: number | null;
      estimated_count: number | null;
      forecast_anchor: boolean;
    }
  >();

  for (const point of sortedPoints) {
    const row = rows.get(point.year) ?? {
      year: point.year,
      actual_price: null,
      estimated_price: null,
      forecast_price: null,
      actual_count: null,
      estimated_count: null,
      forecast_anchor: false
    };
    if (point.kind === "forecast") {
      row.forecast_price = point.avg_price;
    } else if (point.kind === "estimated") {
      row.estimated_price = point.avg_price;
      row.estimated_count = point.transaction_count ?? null;
    } else {
      row.actual_price = point.avg_price;
      row.actual_count = point.transaction_count ?? null;
    }
    rows.set(point.year, row);
  }

  const chartRows = [...rows.values()];
  for (const row of chartRows) {
    if (row.actual_price !== null && row.estimated_price === null) {
      row.estimated_price = row.actual_price;
    }
  }
  const firstForecastIndex = chartRows.findIndex((row) => row.forecast_price !== null);
  if (firstForecastIndex > 0) {
    const anchor = chartRows[firstForecastIndex - 1];
    if (anchor.actual_price !== null) {
      anchor.forecast_price = anchor.actual_price;
      anchor.forecast_anchor = true;
    }
  }

  return chartRows;
}
