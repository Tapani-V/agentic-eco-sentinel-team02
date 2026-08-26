import { useSpareParts } from '../../queries';
import { formatMoney, numberOr0, textOr } from '../../domain/format';
import { availabilityClass } from '../../domain/status';
import { AsyncRegion } from '../common/AsyncRegion';
import { useAnnouncer } from '../common/Announcer';
import { Badge } from '../common/Badge';
import { SummaryCards } from './SummaryCards';
import { useAnnounceOnLoad } from '../../hooks/useAnnounceOnLoad';
import type { SparePartsResponse } from '../../api/types';

/**
 * Spare Parts sub-view inside the Maintenance panel.
 * Shows summary cards (total, in_stock, on_order, critical_parts_unavailable)
 * and a list of spare part rows.
 *
 * Requirements: 17.9, 17.10, 17.11, 17.12, 17.13, 17.14
 */
export function SparePartsView() {
  const query = useSpareParts();
  const { announce } = useAnnouncer();
  useAnnounceOnLoad(query, 'Spare Parts', announce);

  return (
    <AsyncRegion<SparePartsResponse>
      query={query}
      loadingLabel="Loading spare parts…"
      isEmpty={(data) => data.parts.length === 0}
      emptyMessage={<p className="empty-state">No spare parts records</p>}
    >
      {(data) => <SparePartsContent data={data} />}
    </AsyncRegion>
  );
}

function SparePartsContent({ data }: { data: SparePartsResponse }) {
  const cards = [
    { label: 'Total', value: numberOr0(data.total) },
    { label: 'In Stock', value: numberOr0(data.by_availability.in_stock) },
    { label: 'On Order', value: numberOr0(data.by_availability.on_order) },
    { label: 'Critical Unavailable', value: numberOr0(data.critical_parts_unavailable) },
  ];

  return (
    <div className="spare-parts-view">
      <SummaryCards cards={cards} />

      <div className="spare-parts-list">
        {data.parts.map((part, index) => (
          <div key={`${textOr(part.part_name, 'unknown')}-${index}`} className="maintenance-row">
            <span className="maintenance-row__id">
              {textOr(part.part_name, 'Unknown')}
            </span>
            <Badge variant={availabilityClass(part.availability)}>
              {textOr(part.availability, 'UNKNOWN').toUpperCase()}
            </Badge>
            <span className="maintenance-row__field">{textOr(part.equipment_type, 'N/A')}</span>
            <span className="maintenance-row__field">Qty: {numberOr0(part.quantity_available)}</span>
            <span className="maintenance-row__field">{numberOr0(part.lead_time_days)}d</span>
            <span className="maintenance-row__cost">{formatMoney(part.unit_cost, 2)}</span>
            <span className="maintenance-row__field">{textOr(part.criticality, 'UNKNOWN').toUpperCase()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
