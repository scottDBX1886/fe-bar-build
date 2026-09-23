import type { Request, Response, Router } from 'express';

type QueryResult = { rows: Record<string, unknown>[] };
export type Query = (sql: string, values?: unknown[]) => Promise<QueryResult>;

export interface CreateInput {
  interventionId: string;
  studentId: string;
  advisorId: string;
  interventionType: string;
  priority: string;
  actorIdentity: string;
  idempotencyKey: string;
}
export interface TransitionInput {
  interventionId: string;
  expectedVersion: number;
  eventType: string;
  newStatus: string;
  actorIdentity: string;
  note: string | null;
  nextFollowUpAt: string | null;
  outcome: string | null;
  idempotencyKey: string;
}

function transactionResult(rows: Record<string, unknown>[]) {
  const row = rows[0];
  if (!row) throw new Error('Lakebase transaction returned no result');
  return {
    status: String(row.result_status),
    interventionId: String(row.intervention_id),
    version: Number(row.version),
  };
}

export async function createIntervention(query: Query, input: CreateInput) {
  const result = await query('SELECT * FROM student_retention_app.create_intervention($1,$2,$3,$4,$5,$6,$7)', [
    input.interventionId,
    input.studentId,
    input.advisorId,
    input.interventionType,
    input.priority,
    input.actorIdentity,
    input.idempotencyKey,
  ]);
  return transactionResult(result.rows);
}

export async function transitionIntervention(query: Query, input: TransitionInput) {
  const result = await query(
    'SELECT * FROM student_retention_app.transition_intervention($1,$2,$3,$4,$5,$6,$7,$8,$9)',
    [
      input.interventionId,
      input.expectedVersion,
      input.eventType,
      input.newStatus,
      input.actorIdentity,
      input.note,
      input.nextFollowUpAt,
      input.outcome,
      input.idempotencyKey,
    ]
  );
  return transactionResult(result.rows);
}

const identity = (req: Request) => req.header('x-forwarded-email') ?? req.header('x-forwarded-user') ?? '';
const bodyObject = (req: Request): Record<string, unknown> =>
  req.body && typeof req.body === 'object' ? (req.body as Record<string, unknown>) : {};
const requiredString = (body: Record<string, unknown>, key: string): string => {
  const value = body[key];
  if (typeof value !== 'string' || !value) throw new Error(`${key} is required`);
  return value;
};

export function registerWorkflowRoutes(router: Router, lakebase: { query: Query }) {
  router.get('/api/students/:studentId/interventions', async (req: Request, res: Response) => {
    try {
      const actor = identity(req);
      if (!actor) return res.status(401).json({ error: 'Signed-in identity is required' });
      const query = lakebase.query.bind(lakebase);
      const [interventions, events] = await Promise.all([
        query(
          `SELECT * FROM student_retention_app.interventions
               WHERE student_id = $1 AND created_by = $2 ORDER BY updated_at DESC`,
          [req.params.studentId, actor]
        ),
        query(
          `SELECT e.* FROM student_retention_app.intervention_events e
               JOIN student_retention_app.interventions i USING (intervention_id)
               WHERE i.student_id = $1 AND i.created_by = $2 ORDER BY event_at DESC`,
          [req.params.studentId, actor]
        ),
      ]);
      return res.json({ interventions: interventions.rows, events: events.rows });
    } catch (error) {
      return res.status(500).json({ error: error instanceof Error ? error.message : 'Query failed' });
    }
  });

  router.post('/api/interventions', async (req: Request, res: Response) => {
    try {
      const actorIdentity = identity(req);
      if (!actorIdentity) return res.status(401).json({ error: 'Signed-in identity is required' });
      const body = bodyObject(req);
      const outcome = await createIntervention(lakebase.query.bind(lakebase), {
        interventionId: requiredString(body, 'interventionId'),
        studentId: requiredString(body, 'studentId'),
        advisorId: requiredString(body, 'advisorId'),
        interventionType: requiredString(body, 'interventionType'),
        priority: requiredString(body, 'priority'),
        idempotencyKey: requiredString(body, 'idempotencyKey'),
        actorIdentity,
      });
      return res.status(outcome.status === 'replayed' ? 200 : 201).json(outcome);
    } catch (error) {
      return res.status(400).json({ error: error instanceof Error ? error.message : 'Create failed' });
    }
  });

  router.patch('/api/interventions/:interventionId', async (req: Request, res: Response) => {
    try {
      const actorIdentity = identity(req);
      if (!actorIdentity) return res.status(401).json({ error: 'Signed-in identity is required' });
      const body = bodyObject(req);
      const outcome = await transitionIntervention(lakebase.query.bind(lakebase), {
        interventionId: String(req.params.interventionId),
        expectedVersion: Number(body.expectedVersion),
        eventType: requiredString(body, 'eventType'),
        newStatus: requiredString(body, 'newStatus'),
        actorIdentity,
        note: typeof body.note === 'string' ? body.note : null,
        nextFollowUpAt: typeof body.nextFollowUpAt === 'string' ? body.nextFollowUpAt : null,
        outcome: typeof body.outcome === 'string' ? body.outcome : null,
        idempotencyKey: requiredString(body, 'idempotencyKey'),
      });
      return res.status(outcome.status === 'conflict' ? 409 : 200).json(outcome);
    } catch (error) {
      return res.status(400).json({ error: error instanceof Error ? error.message : 'Update failed' });
    }
  });
}
