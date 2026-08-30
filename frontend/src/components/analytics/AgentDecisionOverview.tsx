import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { numberOr0 } from '../../domain/format';
import type { FleetSummary, ProblematicDevice } from '../../api/types';

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend);

type ActionKind = 'URGENT_REPAIR' | 'SCHEDULE_MAINTENANCE';

const ACTIONS: { key: ActionKind; label: string; color: string }[] = [
  { key: 'URGENT_REPAIR', label: 'Urgent Repair', color: '#2962cc' },
  { key: 'SCHEDULE_MAINTENANCE', label: 'Scheduled Maintenance', color: '#00bcd4' },
];

function countTools(devices: ProblematicDevice[], toolName: string): number {
  return devices.filter((device) => device.mcp_tools_used?.includes(toolName)).length;
}

function countActions(devices: ProblematicDevice[], action: ActionKind): number {
  return devices.filter((device) => device.action === action).length;
}

function equipmentTypes(devices: ProblematicDevice[]): string[] {
  return [...new Set(devices.map((device) => device.equipment_type).filter((type): type is string => Boolean(type)))].sort();
}

export function AgentDecisionOverview({ fleet }: { fleet: FleetSummary }): React.JSX.Element {
  const devices = fleet._problematic_devices ?? [];
  const types = equipmentTypes(devices);
  const totalDevices = numberOr0(fleet.total_devices);
  const healthyDevices = numberOr0(fleet.healthy_devices);
  const diagnosisRuns = Math.max(0, totalDevices - healthyDevices);
  const urgentRepairs = countActions(devices, 'URGENT_REPAIR');
  const scheduledMaintenance = countActions(devices, 'SCHEDULE_MAINTENANCE');
  const sparePartChecks = countTools(devices, 'get-spare-parts');
  const maintenanceCalls = countTools(devices, 'schedule-maintenance');
  const workOrderCalls = countTools(devices, 'create-work-order');

  const chartData = {
    labels: types,
    datasets: ACTIONS.map((action) => ({
      label: action.label,
      data: types.map((type) => devices.filter(
        (device) => device.equipment_type === type && device.action === action.key,
      ).length),
      backgroundColor: action.color,
      borderColor: action.color,
      borderWidth: 1,
      borderRadius: 4,
    })),
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true },
      y: {
        stacked: true,
        beginAtZero: true,
        ticks: { precision: 0 },
        title: { display: true, text: 'Devices' },
      },
    },
    plugins: {
      legend: { position: 'bottom' as const },
      tooltip: { mode: 'index' as const, intersect: false },
    },
  };

  return (
    <section className="agent-decision-overview">
      <h4 className="agent-decision-overview__title">Agent Decision Overview</h4>
      <div className="agent-decision-overview__metrics">
        <div className="agent-metric">
          <span className="agent-metric__label">HealthAgent Analyses</span>
          <span className="agent-metric__value">{totalDevices}</span>
        </div>
        <div className="agent-metric">
          <span className="agent-metric__label">DiagnosisAgent Analyses</span>
          <span className="agent-metric__value">{diagnosisRuns}</span>
        </div>
        <div className="agent-metric agent-metric--urgent">
          <span className="agent-metric__label">Urgent Repairs</span>
          <span className="agent-metric__value">{urgentRepairs}</span>
        </div>
        <div className="agent-metric agent-metric--scheduled">
          <span className="agent-metric__label">Maintenance Scheduled</span>
          <span className="agent-metric__value">{scheduledMaintenance}</span>
        </div>
      </div>

      <div className="agent-decision-overview__tools">
        <span>Spare-part validations: <strong>{sparePartChecks}</strong></span>
        <span>Maintenance tool calls: <strong>{maintenanceCalls}</strong></span>
        <span>Work orders created: <strong>{workOrderCalls}</strong></span>
      </div>

      <div className="agent-decision-overview__chart">
        <Bar data={chartData} options={chartOptions} />
      </div>
    </section>
  );
}
