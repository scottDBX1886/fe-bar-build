export interface CaseloadRow {
  student_id: string; advisor_id: string; program_code: string; risk_score: number; risk_tier: string;
  intervention_status: string; caseload_priority: number; follow_up_due: boolean; leading_factors: string[];
}
export async function fetchInterventions(studentId: string) {
  const response = await fetch(`/api/students/${encodeURIComponent(studentId)}/interventions`);
  if (!response.ok) throw new Error(`Unable to load intervention history (${response.status})`);
  return response.json() as Promise<{ interventions: Record<string, unknown>[]; events: Record<string, unknown>[] }>;
}
export async function submitIntervention(body: Record<string, unknown>) {
  const response = await fetch('/api/interventions', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error(`Unable to create intervention (${response.status})`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== 'object' || !('status' in payload)) throw new Error('Invalid intervention response');
  return payload as { status: string; interventionId: string; version: number };
}
