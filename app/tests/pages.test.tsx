import { describe, expect, it } from 'vitest';
import { resolveDataState, fallbackBriefing, sortCaseload } from '../client/src/lib/workflow-state';

describe('workflow states', () => {
  it.each([
    [{ loading: true, error: null, rows: 0 }, 'loading'],
    [{ loading: false, error: 'failed', rows: 0 }, 'error'],
    [{ loading: false, error: null, rows: 0 }, 'empty'],
    [{ loading: false, error: null, rows: 2, stale: true }, 'partial'],
    [{ loading: false, error: null, rows: 2 }, 'ready'],
  ] as const)('resolves %o as %s', (input, expected) => expect(resolveDataState(input)).toBe(expected));

  it('falls back to governed facts when a GenAI briefing is unavailable', () => {
    expect(fallbackBriefing(['Low attendance', 'Missed assignments'])).toContain('Low attendance');
  });

  it('sorts actionable risk and overdue follow-up first', () => {
    const rows = sortCaseload([
      { student_id: 'low', caseload_priority: 2, follow_up_due: false },
      { student_id: 'urgent', caseload_priority: 5, follow_up_due: true },
    ]);
    expect(rows[0].student_id).toBe('urgent');
  });
});
