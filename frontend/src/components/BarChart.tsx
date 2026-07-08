export interface BarChartRow {
  label: string;
  value: number;
}

interface BarChartProps {
  data: BarChartRow[];
  width?: number;
  barHeight?: number;
  valueFormatter?: (v: number) => string;
}

const PADDING_LEFT = 140;
const PADDING_RIGHT = 56;
const BAR_GAP = 14;

function colorForRate(rate: number): string {
  if (rate > 0.9) return "#22c55e";
  if (rate >= 0.7) return "#f59e0b";
  return "#ef4444";
}

export function BarChart({
  data,
  width = 640,
  barHeight = 22,
  valueFormatter = (v) => `${(v * 100).toFixed(1)}%`,
}: BarChartProps) {
  const chartW = width - PADDING_LEFT - PADDING_RIGHT;
  const height = data.length * (barHeight + BAR_GAP) + BAR_GAP;
  const maxValue = Math.max(1, ...data.map((d) => d.value));

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-zinc-500 border border-border rounded-lg h-24">
        No data to compare yet.
      </div>
    );
  }

  return (
    <svg width={width} height={height} className="font-mono select-none">
      {data.map((row, i) => {
        const y = BAR_GAP + i * (barHeight + BAR_GAP);
        const barW = Math.max(2, (row.value / maxValue) * chartW);
        const color = colorForRate(row.value);
        return (
          <g key={row.label}>
            <text x={PADDING_LEFT - 10} y={y + barHeight / 2 + 4} textAnchor="end" fontSize={12} fill="#d4d4d8">
              {row.label}
            </text>
            <rect
              x={PADDING_LEFT}
              y={y}
              width={chartW}
              height={barHeight}
              rx={4}
              fill="#1e1e2e"
            />
            <rect x={PADDING_LEFT} y={y} width={barW} height={barHeight} rx={4} fill={color} />
            <text
              x={PADDING_LEFT + barW + 8}
              y={y + barHeight / 2 + 4}
              fontSize={12}
              fill="#e4e4e7"
            >
              {valueFormatter(row.value)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
