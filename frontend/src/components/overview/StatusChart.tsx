import React from 'react';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { Doughnut } from 'react-chartjs-2';
import { VisuallyHidden } from '../common/VisuallyHidden';

ChartJS.register(ArcElement, Tooltip, Legend);

export interface StatusChartProps {
  healthy: number;
  warning: number;
  critical: number;
}

/** Doughnut chart showing fleet device status distribution. */
export function StatusChart({ healthy, warning, critical }: StatusChartProps): React.JSX.Element {
  const data = {
    labels: ['Healthy', 'Warning', 'Critical'],
    datasets: [
      {
        data: [healthy, warning, critical],
        backgroundColor: ['#00bcd4', '#ffc107', '#455a64'],
        borderColor: '#ffffff',
        borderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom' as const,
      },
    },
  };

  return (
    <>
      <div className="chart-container" style={{ height: '300px' }}>
        <Doughnut data={data} options={options} />
      </div>
      <VisuallyHidden>
        Device status distribution: {healthy} healthy, {warning} warning, {critical} critical
      </VisuallyHidden>
    </>
  );
}
