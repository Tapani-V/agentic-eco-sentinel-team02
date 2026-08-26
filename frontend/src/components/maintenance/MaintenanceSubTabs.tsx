import { useTabKeyboardNav } from '../../hooks/useTabKeyboardNav';

export type SubTabId = 'schedules' | 'work-orders' | 'spare-parts';

export interface SubTabDef {
  id: SubTabId;
  label: string;
}

const SUB_TABS: readonly SubTabDef[] = [
  { id: 'schedules', label: '📅 Schedules' },
  { id: 'work-orders', label: '📋 Work Orders' },
  { id: 'spare-parts', label: '🔧 Spare Parts' },
] as const;

export interface MaintenanceSubTabsProps {
  activeId: SubTabId;
  onSelect: (id: SubTabId) => void;
}

/**
 * Nested tablist for the Maintenance panel sub-views.
 * Reuses the same keyboard navigation pattern as TabNavigator
 * but with subtab CSS classes (.maintenance-subtabs and .subtab-btn).
 */
export function MaintenanceSubTabs({ activeId, onSelect }: MaintenanceSubTabsProps) {
  const tabIds = SUB_TABS.map((t) => t.id);
  const { onKeyDown } = useTabKeyboardNav(tabIds, activeId, onSelect);

  return (
    <div className="maintenance-subtabs" role="tablist" onKeyDown={onKeyDown}>
      {SUB_TABS.map((tab) => {
        const isActive = tab.id === activeId;
        return (
          <button
            key={tab.id}
            id={`subtab-${tab.id}`}
            role="tab"
            aria-selected={isActive}
            aria-controls={`subpanel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            className="subtab-btn"
            onClick={() => onSelect(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
