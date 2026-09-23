import { describe, expect, it, vi } from 'vitest';
import { createIntervention, transitionIntervention } from '../server/interventions';

const result = (rows: unknown[]) => Promise.resolve({ rows });

describe('intervention repository', () => {
  it('maps applied and replayed transaction results', async () => {
    const query = vi
      .fn()
      .mockImplementation(() => result([{ result_status: 'applied', intervention_id: 'i-1', version: 1 }]));
    await expect(
      createIntervention(query, {
        interventionId: 'i-1',
        studentId: 's-1',
        advisorId: 'a-1',
        interventionType: 'outreach',
        priority: 'high',
        actorIdentity: 'a-1',
        idempotencyKey: 'k-1',
      })
    ).resolves.toMatchObject({ status: 'applied', version: 1 });
    expect(query.mock.calls[0][0]).toContain('student_retention_app.create_intervention');
  });

  it('preserves optimistic concurrency conflicts', async () => {
    const query = vi
      .fn()
      .mockImplementation(() => result([{ result_status: 'conflict', intervention_id: 'i-1', version: 4 }]));
    await expect(
      transitionIntervention(query, {
        interventionId: 'i-1',
        expectedVersion: 3,
        eventType: 'updated',
        newStatus: 'in_progress',
        actorIdentity: 'a-1',
        note: null,
        nextFollowUpAt: null,
        outcome: null,
        idempotencyKey: 'k-2',
      })
    ).resolves.toMatchObject({ status: 'conflict', version: 4 });
  });
});
