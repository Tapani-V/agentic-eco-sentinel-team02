export interface HealthReading {
  percent: number;      // integer 0..100
  barWidth: string;     // `${percent}%`
  valid: boolean;       // false when input was absent, non-numeric, or non-finite
}

export function computeHealth(score: unknown): HealthReading {
  if (typeof score !== 'number' || !Number.isFinite(score)) {
    return { percent: 0, barWidth: '0%', valid: false };
  }
  const clamped = Math.min(1, Math.max(0, score));
  const percent = Math.round((1 - clamped) * 100);
  return { percent, barWidth: `${percent}%`, valid: true };
}
