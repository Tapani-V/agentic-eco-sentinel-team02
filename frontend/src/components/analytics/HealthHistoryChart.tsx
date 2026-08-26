import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import type { HealthHistoryResponse } from '../../api/types';

// Register Chart.js components
ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend);

/** Colour mapping by equipment type */
const EQUIPMENT_COLORS: Record<string, string> = {
  PUMP: '#00bcd4',
  MOTOR: '#ffc107',
  COMPRESSOR: '#0097a7',
  GENERATOR: '#455a64',
};

interface HealthHistoryChartProps {
  data: HealthHistoryResponse;
}

interface TypeStats {
  type: string;
  avgHealth: number;
  minHealth: number;
  maxHealth: number;
  deviceCount: number;
  trend: 'improving' | 'stable' | 'worsening';
}

function computeTypeStats(data: HealthHistoryResponse): TypeStats[] {
  const byType: Record<string, { healths: number[]; firstAvg: number; lastAvg: number; count: number }> = {};

  for (const device of data.devices) {
    const type = device.equipment_type;
    if (!byType[type]) {
      byType[type] = { healths: [], firstAvg: 0, lastAvg: 0, count: 0 };
    }

    const points = device.data_points;
    if (points.length > 0) {
      // Use latest health percent for average
      const latest = points[points.length - 1]!.health_percent;
      byType[type]!.healths.push(latest);
      byType[type]!.count++;

      // First and last for trend
      const first = points[0]!.health_percent;
      byType[type]!.firstAvg += first;
      byType[type]!.lastAvg += latest;
    }
  }

  return Object.entries(byType).map(([type, stats]) => {
    const avg = stats.healths.reduce((a, b) => a + b, 0) / stats.healths.length;
    const min = Math.min(...stats.healths);
    const max = Math.max(...stats.healths);
    const firstAvg = stats.firstAvg / stats.count;
    const lastAvg = stats.lastAvg / stats.count;
    const diff = lastAvg - firstAvg;

    let trend: 'improving' | 'stable' | 'worsening' = 'stable';
    if (diff > 3) trend = 'improving';
    else if (diff < -3) trend = 'worsening';

    return { type, avgHealth: Math.round(avg * 10) / 10, minHealth: Math.round(min * 10) / 10, maxHealth: Math.round(max * 10) / 10, deviceCount: stats.count, trend };
  }).sort((a, b) => a.type.localeCompare(b.type));
}

/**
 * Fleet Health History — Aggregated statistics view.
 * Shows average health by equipment type as a bar chart + summary cards.
 */
export function HealthHistoryChart({ data }: HealthHistoryChartProps) {
  const stats = computeTypeStats(data);

  const chartData = {
    labels: stats.map(s => s.type),
    datasets: [
      {
        label: 'Avg Health %',
        data: stats.map(s => s.avgHealth),
        backgroundColor: stats.map(s => EQUIPMENT_COLORS[s.type] || '#999'),
        borderColor: stats.map(s => EQUIPMENT_COLORS[s.type] || '#999'),
        borderWidth: 1,
        borderRadius: 6,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        type: 'linear' as const,
        min: 0,
        max: 100,
        title: { display: true, text: 'Health %' },
      },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (item: any) => {
            const stat = stats[item.dataIndex];
            if (!stat) return '';
            return [
              `Avg: ${stat.avgHealth}%`,
              `Range: ${stat.minHealth}% – ${stat.maxHealth}%`,
              `Devices: ${stat.deviceCount}`,
              `Trend: ${stat.trend}`,
            ];
          },
        },
      },
      legend: { display: false },
    },
  };

  const trendIcon = (t: string) => {
    if (t === 'improving') return '↓ Improving';
    if (t === 'worsening') return '↑ Worsening';
    return '→ Stable';
  };

  const trendClass = (t: string) => {
    if (t === 'improving') return 'memory-trend--improving';
    if (t === 'worsening') return 'memory-trend--worsening';
    return 'memory-trend--stable';
  };

  return (
    <div>
      {/* Summary cards per equipment type */}
      <div className="health-stats-grid">
        {stats.map(s => (
          <div key={s.type} className="health-stat-card">
            <div className="health-stat-card__type">{s.type}</div>
            <div className="health-stat-card__value">{s.avgHealth}%</div>
            <div className="health-stat-card__detail">
              {s.deviceCount} devices · {s.minHealth}%–{s.maxHealth}%
            </div>
            <div className={`health-stat-card__trend ${trendClass(s.trend)}`}>
              {trendIcon(s.trend)}
            </div>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      <div style={{ height: '250px', position: 'relative', marginTop: '16px' }}>
        <Bar data={chartData} options={options} />
      </div>
    </div>
  );
}
