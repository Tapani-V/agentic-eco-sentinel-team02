import { useState } from 'react';
import { type TabId } from './config/queryKeys';
import { AppHeader, AppFooter, Container } from './components/layout';
import { KpiPanel } from './components/kpi';
import { TabNavigator, TabPanel } from './components/tabs';
import { PanelErrorBoundary, AnnouncerProvider } from './components/common';
import { OverviewPanel } from './components/overview';
import { DevicesPanel } from './components/devices';
import { AlertsPanel } from './components/alerts';
import { MaintenancePanel } from './components/maintenance';
import { AnalyticsPanel } from './components/analytics';
import { LastUpdatedProvider } from './queries/useLastUpdated';

const TABS = [
  { id: 'overview' as const, label: 'Overview' },
  { id: 'devices' as const, label: 'Devices' },
  { id: 'alerts' as const, label: 'Alerts' },
  { id: 'maintenance' as const, label: 'Maintenance' },
  { id: 'analytics' as const, label: 'Analytics' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  return (
    <LastUpdatedProvider>
      <AnnouncerProvider>
        <Container>
          <AppHeader activeTab={activeTab} />
          <KpiPanel />
          <TabNavigator tabs={TABS} activeId={activeTab} onSelect={setActiveTab} />
          <PanelErrorBoundary key={activeTab}>
            <TabPanel id={activeTab}>
              {activeTab === 'overview' && <OverviewPanel />}
              {activeTab === 'devices' && <DevicesPanel />}
              {activeTab === 'alerts' && <AlertsPanel />}
              {activeTab === 'maintenance' && <MaintenancePanel />}
              {activeTab === 'analytics' && <AnalyticsPanel />}
            </TabPanel>
          </PanelErrorBoundary>
          <AppFooter />
        </Container>
      </AnnouncerProvider>
    </LastUpdatedProvider>
  );
}
