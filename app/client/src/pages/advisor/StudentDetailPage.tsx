import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { sql } from '@databricks/appkit-ui/js';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  useAnalyticsQuery,
} from '@databricks/appkit-ui/react';
import { DataState } from '../../components/DataState';
import { fallbackBriefing } from '../../lib/workflow-state';
import { fetchInterventions } from '../../lib/workflows';
import { InterventionWorkflow } from './InterventionWorkflow';

const text = (value: unknown) => (typeof value === 'string' ? value : '');
export function StudentDetailPage() {
  const { studentId = '' } = useParams();
  const params = useMemo(() => ({ studentId: sql.string(studentId) }), [studentId]);
  const detail = useAnalyticsQuery('student_detail', params);
  const student = detail.data?.[0];
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const loadEvents = () => {
    void fetchInterventions(studentId).then((value) => setEvents(value.events));
  };
  useEffect(loadEvents, [studentId]);
  const factors = text(student?.leading_factors).split(',').filter(Boolean);
  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">Advisor workflow</p>
        <h2 className="text-3xl font-semibold">Student {studentId}</h2>
      </div>
      <DataState loading={detail.loading} error={detail.error} rows={student ? 1 : 0}>
        {student && (
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Governed student facts</CardTitle>
                <CardDescription>Latest score · protected audit attributes excluded</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <div>
                  <span className="text-muted-foreground">Risk</span>
                  <p>
                    <Badge variant="secondary">
                      {text(student.risk_tier)} · {(Number(student.risk_score) * 100).toFixed(0)}%
                    </Badge>
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Program</span>
                  <p>{text(student.program_code)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Attendance, 28d</span>
                  <p>{(Number(student.attendance_rate_28d) * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Missed assignments, 28d</span>
                  <p>{Number(student.missed_assignments_28d)}</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Advisor briefing</CardTitle>
                <CardDescription>Verify before acting</CardDescription>
              </CardHeader>
              <CardContent className="text-sm">{fallbackBriefing(factors)}</CardContent>
            </Card>
            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle>Intervention timeline</CardTitle>
                <CardDescription>Immutable Lakebase events</CardDescription>
              </CardHeader>
              <CardContent>
                {events.length ? (
                  events.map((event) => (
                    <div className="border-l pl-4 py-2 text-sm" key={String(event.event_id)}>
                      {String(event.event_type)} · {String(event.new_status)} · {String(event.event_at)}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No intervention events yet.</p>
                )}
              </CardContent>
            </Card>
            <div className="lg:col-span-3">
              <InterventionWorkflow studentId={studentId} advisorId={text(student.advisor_id)} onSaved={loadEvents} />
            </div>
          </div>
        )}
      </DataState>
    </section>
  );
}
