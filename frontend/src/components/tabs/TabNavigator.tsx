import { useTabKeyboardNav } from '../../hooks/useTabKeyboardNav';

export interface TabDef<T extends string = string> {
  id: T;
  label: string;
}

export interface TabNavigatorProps<T extends string = string> {
  tabs: TabDef<T>[];
  activeId: T;
  onSelect: (id: T) => void;
}

/**
 * Renders a role="tablist" container with tab buttons following WAI-ARIA Tabs pattern.
 * Supports roving tabIndex and keyboard navigation (ArrowLeft/Right, Home, End).
 */
export function TabNavigator<T extends string = string>({
  tabs,
  activeId,
  onSelect,
}: TabNavigatorProps<T>) {
  const tabIds = tabs.map((t) => t.id);
  const { onKeyDown } = useTabKeyboardNav(tabIds, activeId, onSelect);

  return (
    <div className="tabs" role="tablist" onKeyDown={onKeyDown}>
      {tabs.map((tab) => {
        const isActive = tab.id === activeId;
        return (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            className="tab-btn"
            onClick={() => onSelect(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
