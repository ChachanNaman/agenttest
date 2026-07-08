import { useMemo, useState } from "react";

export interface LineChartPoint {
  label: string;
  value: number;
  meetsThreshold?: boolean;
}

interface LineChartProps {
  data: LineChartPoint[];
  width?: number;
  height?: number;
  threshold?: number;
  valueFormatter?: (v: number) => string;
  color?: string;
  yMax?: number;
}

const PADDING = { top: 16, right: 16, bottom: 28, left: 44 };
const GRID_STEPS = [0, 0.25, 0.5, 0.75, 1];

export function LineChart({
  data,
  width = 640,
  height = 260,
  threshold,
  valueFormatter = (v) => `${(v * 100).toFixed(0)}%`,
  color = "#6366f1",
  yMax = 1,
}: LineChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const chartW = width - PADDING.left - PADDING.right;
  const chartH = height - PADDING.top - PADDING.bottom;

  const xScale = (i: number) => (data.length <= 1 ? 0 : (i / (data.length - 1)) * chartW);
  const yScale = (v: number) => chartH - (v / yMax) * chartH;

  const linePath = useMemo(() => {
    if (data.length === 0) return "";
    return data.reduce((acc, d, i) => {
      const x = xScale(i) + PADDING.left;
      const y = yScale(d.value) + PADDING.top;
      if (i === 0) return `M ${x} ${y}`;
      const px = xScale(i - 1) + PADDING.left;
      const py = yScale(data[i - 1].value) + PADDING.top;
      const cpX = (px + x) / 2;
      return `${acc} C ${cpX} ${py} ${cpX} ${y} ${x} ${y}`;
    }, "");
  }, [data, chartW, chartH]);

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-sm text-zinc-500 border border-border rounded-lg"
        style={{ width, height }}
      >
        No history yet — run this test to start collecting data.
      </div>
    );
  }

  const hovered = hoverIndex !== null ? data[hoverIndex] : null;

  return (
    <svg
      width={width}
      height={height}
      className="font-mono select-none"
      onMouseLeave={() => setHoverIndex(null)}
    >
      {GRID_STEPS.map((step) => {
        const y = yScale(step * yMax) + PADDING.top;
        return (
          <g key={step}>
            <line
              x1={PADDING.left}
              x2={width - PADDING.right}
              y1={y}
              y2={y}
              stroke="#1e1e2e"
              strokeWidth={1}
            />
            <text x={PADDING.left - 8} y={y + 3} textAnchor="end" fontSize={10} fill="#71717a">
              {valueFormatter(step * yMax)}
            </text>
          </g>
        );
      })}

      {threshold !== undefined && (
        <line
          x1={PADDING.left}
          x2={width - PADDING.right}
          y1={yScale(threshold) + PADDING.top}
          y2={yScale(threshold) + PADDING.top}
          stroke="#f59e0b"
          strokeWidth={1.5}
          strokeDasharray="4 4"
        />
      )}

      <path d={linePath} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" />

      {data.map((d, i) => {
        const x = xScale(i) + PADDING.left;
        const y = yScale(d.value) + PADDING.top;
        const pointColor = d.meetsThreshold === false ? "#ef4444" : d.meetsThreshold === true ? "#22c55e" : color;
        return (
          <g key={i}>
            <circle
              cx={x}
              cy={y}
              r={hoverIndex === i ? 5 : 3.5}
              fill={pointColor}
              stroke="#0a0a0f"
              strokeWidth={1.5}
            />
            <rect
              x={x - (chartW / Math.max(data.length, 1)) / 2}
              y={PADDING.top}
              width={chartW / Math.max(data.length, 1)}
              height={chartH}
              fill="transparent"
              onMouseEnter={() => setHoverIndex(i)}
            />
          </g>
        );
      })}

      {data.length > 1 && (
        <>
          <text x={PADDING.left} y={height - 8} fontSize={10} fill="#71717a">
            {data[0].label}
          </text>
          <text x={width - PADDING.right} y={height - 8} fontSize={10} fill="#71717a" textAnchor="end">
            {data[data.length - 1].label}
          </text>
        </>
      )}

      {hovered && hoverIndex !== null && (
        <g>
          <line
            x1={xScale(hoverIndex) + PADDING.left}
            x2={xScale(hoverIndex) + PADDING.left}
            y1={PADDING.top}
            y2={chartH + PADDING.top}
            stroke="#3f3f4a"
            strokeWidth={1}
          />
          <foreignObject
            x={Math.min(Math.max(xScale(hoverIndex) + PADDING.left - 55, 0), width - 110)}
            y={Math.max(yScale(hovered.value) + PADDING.top - 46, 0)}
            width={110}
            height={38}
          >
            <div className="bg-card border border-border rounded-md px-2 py-1 text-xs shadow-lg">
              <div className="text-zinc-300">{hovered.label}</div>
              <div className="font-semibold" style={{ color }}>
                {valueFormatter(hovered.value)}
              </div>
            </div>
          </foreignObject>
        </g>
      )}
    </svg>
  );
}
