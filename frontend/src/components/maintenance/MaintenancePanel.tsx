import { useState } from 'react';
import { MaintenanceSubTabs, type SubTabId } from './MaintenanceSubTabs';
import { SparePartsView } from './SparePartsView';
import { WorkOrdersView } from './WorkOrdersView';
import { SchedulesView } from './SchedulesView';

/**
 * Maintenance tab panel with three sub-views behind a nested tablist.
 * Only the selected sub-view is mounted, so its query interval is suspended
 * when inactive (requirement 6.6).
 */
export function MaintenancePanel() {
  const [activeSubTab, setActiveSubTab] = useState<SubTabId>('schedules');

  return (
    <div className="maintenance-panel">
      <MaintenanceSubTabs activeId={activeSubTab} onSelect={setActiveSubTab} />

      <div
        id={`subpanel-${activeSubTab}`}
        role="tabpanel"
        aria-labelledby={`subtab-${activeSubTab}`}
      >
        {activeSubTab === 'schedules' && <SchedulesView />}
        {activeSubTab === 'work-orders' && <WorkOrdersView />}
        {activeSubTab === 'spare-parts' && <SparePartsView />}
      </div>
    </div>
  );
}
