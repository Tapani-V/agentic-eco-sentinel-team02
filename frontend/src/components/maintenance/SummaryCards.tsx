export interface SummaryCardEntry {
  label: string;
  value: string | number;
  color?: 'red' | 'gold' | 'blue' | 'default';
}

export interface SummaryCardsProps {
  cards: SummaryCardEntry[];
}

/**
 * Renders a .summary-cards grid with one card per entry showing label above value,
 * with a colored left border.
 */
export function SummaryCards({ cards }: SummaryCardsProps) {
  return (
    <div className="summary-cards">
      {cards.map((card) => (
        <div key={card.label} className={`summary-card summary-card--${card.color ?? 'default'}`}>
          <div className="summary-card__label">{card.label}</div>
          <div className="summary-card__value">{card.value}</div>
        </div>
      ))}
    </div>
  );
}
