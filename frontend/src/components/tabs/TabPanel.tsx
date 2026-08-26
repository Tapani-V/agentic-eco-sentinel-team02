import type { ReactNode } from 'react';

export interface TabPanelProps {
  id: string;
  children: ReactNode;
}

/**
 * Renders a role="tabpanel" container linked to its tab button via aria-labelledby.
 * Applies the "tab-panel" class for the ported fade-in animation.
 */
export function TabPanel({ id, children }: TabPanelProps) {
  return (
    <div
      id={`panel-${id}`}
      role="tabpanel"
      aria-labelledby={`tab-${id}`}
      className="tab-panel"
    >
      {children}
    </div>
  );
}
