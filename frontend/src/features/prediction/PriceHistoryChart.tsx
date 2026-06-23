import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PriceHistoryPoint } from "../../types/assets";

type Props = {
  points: PriceHistoryPoint[];
};

export function PriceHistoryChart({ points }: Props) {
  return (
    <section className="panel chart-panel">
      <h2>価格推移</h2>
      {points.length === 0 ? (
        <p className="muted">価格推移データがありません。</p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={points}>
            <XAxis dataKey="year" />
            <YAxis tickFormatter={(value) => `${Math.round(Number(value) / 10000)}万`} />
            <Tooltip formatter={(value) => `${Math.round(Number(value) / 10000)}万円`} />
            <Line type="monotone" dataKey="avg_price" stroke="#1d4ed8" strokeWidth={2} dot />
          </LineChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
