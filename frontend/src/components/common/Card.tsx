import React from 'react';

export interface CardProps {
  /** Optional card title */
  title?: string;
  /** Card content */
  children: React.ReactNode;
  /** Additional CSS class */
  className?: string;
}

/** Generic card wrapper with optional title. */
export function Card({ title, children, className }: CardProps): React.JSX.Element {
  return (
    <div className={`card${className ? ` ${className}` : ''}`}>
      {title && <h3 className="card__title">{title}</h3>}
      {children}
    </div>
  );
}
