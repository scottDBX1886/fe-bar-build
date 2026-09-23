export type StateInput = { loading: boolean; error: string | null; rows: number; stale?: boolean };
export function resolveDataState(input: StateInput): 'loading' | 'error' | 'empty' | 'partial' | 'ready' {
  if (input.loading) return 'loading';
  if (input.error) return 'error';
  if (input.rows === 0) return 'empty';
  return input.stale ? 'partial' : 'ready';
}
export const fallbackBriefing = (factors: string[]) =>
  factors.length ? `AI briefing unavailable. Governed risk factors: ${factors.join(', ')}.` : 'AI briefing unavailable; review governed student facts below.';

export function sortCaseload<T extends { caseload_priority: number; follow_up_due: boolean }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => Number(b.follow_up_due) - Number(a.follow_up_due) || b.caseload_priority - a.caseload_priority);
}
