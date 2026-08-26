import { useWorkOrders } from '../../queries';
import { numberOr0, textOr } from '../../domain/format';
import { AsyncRegion } from '../common/AsyncRegion';
import { useAnnouncer } from '../common/Announcer';
import { Badge } from '../common/Badge';
import { SummaryCards } from './SummaryCards';
import { useAnnounceOnLoad } from '../../hooks/useAnnounceOnLoad';
import type { WorkOrdersResponse } from '../../api/types';

/**
 * Work Orders sub-view inside the Maintenance panel.
 * Shows summary cards and a table of work order rows.
 * Requirements: 17.7, 17.8, 17.12, 17.13, 17.14
 */
export function WorkOrdersView() {
  const query = useWorkOrders();
  const { announce } = useAnnouncer();
  useAnnounceOnLoad(query, 'Work Orders', announce);

  return (
    <AsyncRegion<WorkOrdersResponse>
      query={query}
      loadingLabel="Loading work orders…"
      isEmpty={(data) => data.work_orders.length === 0}
      emptyMessage={<p className="empty-state">No work orders</p>}
    >
      {(data) => (
        <div className="work-orders-view">
          <SummaryCards
            cards={[
              { label: 'Total', value: numberOr0(data.total) },
              { label: 'Immediate', value: numberOr0(data.by_urgency.immediate) },
              { label: 'Urgent', value: numberOr0(data.by_urgency.urgent) },
              { label: 'Est. Hours', value: `${numberOr0(data.total_estimated_hours)}h` },
            ]}
          />

          <div className="maintenance-list">
            {data.work_orders.map((wo, idx) => (
              <div key={textOr(wo.work_order_id, `wo-${idx}`)} className="maintenance-row">
                <span className="maintenance-row__id">{textOr(wo.work_order_id, '—')}</span>
                <span className="maintenance-row__device">{textOr(wo.device_id, '—')}</span>
                <Badge variant={textOr(wo.urgency, 'unknown').toLowerCase()}>
                  {textOr(wo.urgency, '—').toUpperCase()}
                </Badge>
                <span className="maintenance-row__desc">{textOr(wo.description, '—')}</span>
                <span className="maintenance-row__assigned">{textOr(wo.assigned_to, '—')}</span>
                <span className="maintenance-row__hours">{numberOr0(wo.estimated_hours)}h</span>
                <span className="maintenance-row__date">{textOr(wo.created_at, '—')}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </AsyncRegion>
  );
}
