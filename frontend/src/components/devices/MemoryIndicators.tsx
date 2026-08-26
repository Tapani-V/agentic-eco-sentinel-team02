import type { DeviceMemoryContext } from '../../api/types';

interface MemoryIndicatorsProps {
  context: DeviceMemoryContext | undefined | null;
}

/**
 * Renders memory-sourced indicators on a device card:
 * - History count badge (📚 N)
 * - Trend arrow (↓ improving / → stable / ↑ worsening)
 * - Recurring issue chip (🔁 Recurring)
 *
 * Returns null if context is undefined/null (backward compatible).
 */
export function MemoryIndicators({ context }: MemoryIndicatorsProps) {
  if (!context) {
    return null;
  }

  return (
    <div className="device-card__memory" aria-label="Memory indicators">
      {context.history_count > 0 && (
        <span className="memory-badge" title={`${context.history_count} diagnosis entries stored`}>
          📚 {context.history_count}
        </span>
      )}

      {context.trend && (
        <span className={`memory-trend memory-trend--${context.trend}`} title={`Trend: ${context.trend}`}>
          {context.trend === 'improving' && '↓'}
          {context.trend === 'stable' && '→'}
          {context.trend === 'worsening' && '↑'}
          {' '}{context.trend}
        </span>
      )}

      {context.is_recurring && (
        <span className="memory-recurring" title="Recurring issue detected">
          🔁 Recurring
        </span>
      )}
    </div>
  );
}
