import React from 'react';

export interface VisuallyHiddenProps {
  /** Content visible only to assistive technology */
  children: React.ReactNode;
  /** Optional element type, defaults to span */
  as?: 'span' | 'div';
}

/** Wraps content in a .sr-only element, visible only to screen readers. */
export function VisuallyHidden({ children, as: Element = 'span' }: VisuallyHiddenProps): React.JSX.Element {
  return <Element className="sr-only">{children}</Element>;
}
