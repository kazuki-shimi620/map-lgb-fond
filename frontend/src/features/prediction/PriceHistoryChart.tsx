import { Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PriceHistoryPoint } from "../../types/assets";

type Props = {
  points: PriceHistoryPoint[];
};

export function PriceHistoryChart({ points }: Props) {
  const chartData = buildChartData(points);

  return (
    <section className="panel chart-panel">
      <h2>価格推移</h2>
      {points.length === 0 ? (
        <p className="muted">価格推移データがありません。</p>
      ) : (
        <div className="chart-scroll">
          <div className="chart-canvas">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData} margin={{ top: 12, right: 12, bottom: 8, left: 4 }}>
                <XAxis dataKey="year" interval="preserveStartEnd" tickMargin={8} />
                <YAxis
                  width={64}
                  tickMargin={8}
                  tickFormatter={(value) => `${Math.round(Number(value) / 10000)}万`}
                />
                <Tooltip formatter={(value) => `${Math.round(Number(value) / 10000)}万円`} />
                <Legend />
                <Line
                  name="実績"
                  type="monotone"
                  dataKey="actual_price"
                  stroke="#1d4ed8"
                  strokeWidth={2}
                  dot
                  connectNulls
                />
                <Line
                  name="予測"
                  type="monotone"
                  dataKey="forecast_price"
                  stroke="#d97706"
                  strokeWidth={2}
                  strokeDasharray="6 5"
                  dot
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}

function buildChartData(points: PriceHistoryPoint[]) {
  const sortedPoints = [...points].sort((a, b) => a.year - b.year);
  const hasForecast = sortedPoints.some((point) => point.kind === "forecast");
  const lastActualYear = [...sortedPoints].reverse().find((point) => point.kind !== "forecast")?.year;

  return sortedPoints.map((point) => {
    const isForecast = point.kind === "forecast";
    const isForecastStart = hasForecast && point.year === lastActualYear;

    return {
      year: point.year,
      actual_price: isForecast ? null : point.avg_price,
      forecast_price: isForecast || isForecastStart ? point.avg_price : null
    };
  });
}
