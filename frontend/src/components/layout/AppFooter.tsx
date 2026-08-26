import { useLastUpdated } from '../../queries/useLastUpdated';
import { useStatus } from '../../queries';
import { formatClockTime, textOr } from '../../domain/format';

export function AppFooter() {
  const lastUpdatedAt = useLastUpdated();
  const { data: status } = useStatus();

  const timeLabel = lastUpdatedAt
    ? `Last updated: ${formatClockTime(new Date(lastUpdatedAt))}`
    : 'Last updated: just now';

  const versionLabel = `Dashboard ${textOr(status?.dashboard?.version, 'version unavailable')}`;

  return (
    <footer className="app-footer">
      <div className="container app-footer__inner">
        <span className="app-footer__updated">{timeLabel}</span>
        <span className="app-footer__version">{versionLabel}</span>
      </div>
    </footer>
  );
}
