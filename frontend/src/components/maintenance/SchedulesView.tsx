import { useMaintenanceSchedule } from '../../queries';
import { formatMoney, numberOr0, textOr } from '../../domain/format';
import { AsyncRegion } from '../common/AsyncRegion';
import { useAnnouncer } from '../common/Announcer';
import { Badge } from '../common/Badge';
import { SummaryCards } from './SummaryCards';
import { useAnnounceOnLoad } from '../../hooks/useAnnounceOnLoad';
import type { MaintenanceScheduleResponse } from '../../api/types';

/**
 * Schedules sub-view inside the Maintenance panel.
 * Shows summary cards (urgent count, scheduled count, total estimated cost)
 * and a list of maintenance schedule rows.
 *
 * Requirements: 17.4, 17.5, 17.6, 17.12, 17.13, 17.14
 */
export function SchedulesView() {
  const query = useMaintenanceSchedule();
  const { announce } = useAnnouncer();
  useAnnounceOnLoad(query, 'Schedules', announce);

  return (
    <AsyncRegion<MaintenanceScheduleResponse>
      query={query}
      loadingLabel="Loading maintenance schedules…"
    >
      {(data) => <SchedulesContent data={data} />}
    </AsyncRegion>
  );
}

function SchedulesContent({ data }: { data: MaintenanceScheduleResponse }) {
  const cards = [
    { label: 'Urgent', value: numberOr0(data.by_priority.urgent), color: 'red' as const },
    { label: 'Scheduled', value: numberOr0(data.by_priority.scheduled), color: 'gold' as const },
    { label: 'Total Cost', value: formatMoney(data.total_estimated_cost, 0), color: 'blue' as const },
  ];

  return (
    <div className="schedules-view card">
      <h3 className="card__title">⚙️ Maintenance Schedule</h3>
      <SummaryCards cards={cards} />

      {data.schedules.length === 0 ? (
        <p className="empty-state">No maintenance schedules</p>
      ) : (
        <div className="schedules-list">
          {data.schedules.map((schedule, index) => {
            const partsNeeded = schedule.parts_needed;
            const partsLine =
              partsNeeded && partsNeeded.length > 0
                ? partsNeeded.join(', ')
                : null;

            return (
              <div key={`${textOr(schedule.device_id, 'unknown')}-${index}`} className="maintenance-row">
                <span className="maintenance-row__id">
                  {textOr(schedule.device_id, 'Unknown')}
                </span>
                <Badge variant={textOr(schedule.priority, 'unknown')}>
                  {textOr(schedule.priority, 'UNKNOWN').toUpperCase()}
                </Badge>
                <span className="maintenance-row__field">{textOr(schedule.reason, 'No reason')}</span>
                <span className="maintenance-row__field">{textOr(schedule.start_date, 'N/A')}</span>
                <span className="maintenance-row__field">{numberOr0(schedule.duration_hours)}h</span>
                <span className="maintenance-row__cost">{formatMoney(schedule.estimated_cost, 2)}</span>
                {partsLine && (
                  <span className="maintenance-row__field">Parts: {partsLine}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
