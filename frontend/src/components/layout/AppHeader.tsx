import { useQueryClient } from '@tanstack/react-query';
import { queryKeys, TAB_QUERY_KEYS, type TabId } from '../../config/queryKeys';
import { HardRefreshButton } from './HardRefreshButton';
import { FreshnessIndicator } from './FreshnessIndicator';

interface AppHeaderProps {
  activeTab: TabId;
  onRefresh?: () => void;
}

export function AppHeader({ activeTab, onRefresh }: AppHeaderProps) {
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    // Invalidate fleet-summary plus the active tab's keys
    queryClient.invalidateQueries({ queryKey: queryKeys.fleetSummary });
    const tabKeys = TAB_QUERY_KEYS[activeTab];
    for (const key of tabKeys) {
      queryClient.invalidateQueries({ queryKey: key });
    }
    onRefresh?.();
  };

  return (
    <header className="app-header">
      <div className="header-left">
        <h1 className="header-title">
          🌍 <span className="text-gradient">Agentic Eco Sentinel</span>
        </h1>
        <p className="header-subtitle">
          Real-time Fleet Monitoring with Multi-Agent Intelligence
        </p>
      </div>
      <div className="header-controls">
        <HardRefreshButton />
        <button className="btn-refresh" onClick={handleRefresh}>
          🔄 Refresh
        </button>
        <span className="live-indicator">
          <span className="live-dot" aria-hidden="true" />
          Live
        </span>
        <FreshnessIndicator />
      </div>
    </header>
  );
}
