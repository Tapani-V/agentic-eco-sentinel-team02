import { useLastUpdated } from '../../queries/useLastUpdated';
import { useElapsed } from '../../hooks/useElapsed';
import { FRESHNESS_TICK_MS } from '../../config/intervals';
import { formatFreshness } from '../../domain/format';

export function FreshnessIndicator() {
  const lastUpdatedAt = useLastUpdated();
  const now = useElapsed(FRESHNESS_TICK_MS);

  const elapsed = lastUpdatedAt != null ? now - lastUpdatedAt : 0;
  const label = `Last updated: ${formatFreshness(elapsed)}`;

  return <span className="freshness-indicator">{label}</span>;
}
