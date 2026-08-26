const EQUIPMENT_TYPES = ['ALL', 'PUMP', 'MOTOR', 'COMPRESSOR', 'GENERATOR'] as const;
type EquipmentType = (typeof EQUIPMENT_TYPES)[number];

const TYPE_LABELS: Record<EquipmentType, string> = {
  ALL: 'All',
  PUMP: 'Pumps',
  MOTOR: 'Motors',
  COMPRESSOR: 'Compressors',
  GENERATOR: 'Generators',
};

const INDIVIDUAL_TYPES = EQUIPMENT_TYPES.filter(t => t !== 'ALL');

interface EquipmentTypeFilterProps {
  activeTypes: Set<string>;
  onToggle: (type: string) => void;
}

/**
 * Toggle buttons for filtering the health history chart by equipment type.
 * Active buttons use --primary-blue background; inactive use --bg-surface.
 * Toggling updates dataset visibility via the parent's state management.
 */
export function EquipmentTypeFilter({ activeTypes, onToggle }: EquipmentTypeFilterProps) {
  return (
    <div className="equipment-filter" role="group" aria-label="Equipment type filter">
      {EQUIPMENT_TYPES.map(type => {
        const isActive =
          type === 'ALL'
            ? INDIVIDUAL_TYPES.every(t => activeTypes.has(t))
            : activeTypes.has(type);

        return (
          <button
            key={type}
            className={`equipment-filter__btn ${isActive ? 'equipment-filter__btn--active' : ''}`}
            onClick={() => onToggle(type)}
            aria-pressed={isActive}
          >
            {TYPE_LABELS[type]}
          </button>
        );
      })}
    </div>
  );
}
