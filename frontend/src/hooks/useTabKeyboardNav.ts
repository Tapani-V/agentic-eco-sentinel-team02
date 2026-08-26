import type { KeyboardEvent } from 'react';

/**
 * Handles ArrowLeft/ArrowRight (wrapping), Home, and End keyboard navigation
 * for a tablist following the WAI-ARIA Tabs pattern with roving tabIndex.
 */
export function useTabKeyboardNav<T extends string>(
  tabIds: readonly T[],
  activeId: T,
  onSelect: (id: T) => void,
): { onKeyDown: (e: KeyboardEvent) => void } {
  const onKeyDown = (e: KeyboardEvent) => {
    const currentIndex = tabIds.indexOf(activeId);
    if (currentIndex === -1) return;

    let nextIndex: number | null = null;

    switch (e.key) {
      case 'ArrowRight':
        nextIndex = (currentIndex + 1) % tabIds.length;
        break;
      case 'ArrowLeft':
        nextIndex = (currentIndex - 1 + tabIds.length) % tabIds.length;
        break;
      case 'Home':
        nextIndex = 0;
        break;
      case 'End':
        nextIndex = tabIds.length - 1;
        break;
      default:
        return;
    }

    e.preventDefault();
    const nextId = tabIds[nextIndex];
    if (nextId !== undefined) {
      onSelect(nextId);
      // Move focus to the newly selected tab button
      const target = (e.currentTarget as HTMLElement).querySelector<HTMLElement>(
        `[id="tab-${nextId}"]`,
      );
      target?.focus();
    }
  };

  return { onKeyDown };
}
