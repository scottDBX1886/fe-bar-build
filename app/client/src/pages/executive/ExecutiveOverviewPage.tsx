import { Card, CardContent, CardDescription, CardHeader, CardTitle, Progress, useAnalyticsQuery } from '@databricks/appkit-ui/react';
import { DataState } from '../../components/DataState';

const parameters = {};
const percent = (value: unknown) => `${(Number(value) * 100).toFixed(1)}%`;
const number = (value: unknown) => Number(value).toLocaleString();
const text = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value) : 'Unknown';

function Kpi({ label, value, context }: { label: string; value: string; context: string }) {
  return <Card><CardHeader><CardDescription>{label}</CardDescription><CardTitle className="text-3xl">{value}</CardTitle></CardHeader><CardContent className="text-xs text-muted-foreground">{context}</CardContent></Card>;
}

export function ExecutiveOverviewPage() {
  const kpis = useAnalyticsQuery('executive_kpis', parameters);
  const trends = useAnalyticsQuery('executive_trends', parameters);
  const row = kpis.data?.[0];
  const freshness = text(row?.data_freshness_at);
  const stale = !row?.data_freshness_at;
  return (
    <section className="mx-auto max-w-7xl space-y-6" aria-labelledby="executive-heading">
      <div>
        <p className="text-sm font-medium text-muted-foreground">Student retention</p>
        <h2 id="executive-heading" className="text-3xl font-semibold tracking-tight text-foreground">
          Executive Overview
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Aggregate decision support only. Student-level records are intentionally excluded from this view.
        </p>
      </div>
      <DataState loading={kpis.loading || trends.loading} error={kpis.error ?? trends.error} rows={row ? 1 : 0} stale={stale}>
        {row && <><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Retention rate" value={percent(row.retention_rate)} context={`Score date ${text(row.score_date)} · Source: Gold`} />
          <Kpi label="Students at risk" value={number(row.at_risk_count)} context={`${number(row.student_count)} students · Score date ${text(row.score_date)}`} />
          <Kpi label="Intervention coverage" value={percent(row.intervention_coverage)} context={`Current score period · Fresh ${freshness}`} />
          <Kpi label="Estimated tuition exposure" value={`$${number(row.estimated_next_term_net_tuition_exposure)}`} context="Next-term estimate, not realized loss · Source: Gold" />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card><CardHeader><CardTitle>Response and follow-up</CardTitle><CardDescription>Current score period</CardDescription></CardHeader><CardContent className="space-y-5">
            <div><div className="mb-2 flex justify-between text-sm"><span>Follow-up completion</span><span>{percent(row.follow_up_completion_rate)}</span></div><Progress value={Number(row.follow_up_completion_rate) * 100} /></div>
            <div className="text-sm"><span className="font-medium">Time to first intervention:</span> {Number(row.time_to_first_intervention_days).toFixed(1)} days</div>
          </CardContent></Card>
          <Card><CardHeader><CardTitle>Risk trend</CardTitle><CardDescription>Honest zero-based scale by score date</CardDescription></CardHeader><CardContent className="space-y-3">
            {(trends.data ?? []).slice(-8).map((item) => <div key={`${text(item.score_date)}-${text(item.risk_tier)}`}><div className="flex justify-between text-xs"><span>{text(item.score_date)} · {text(item.risk_tier)}</span><span>{percent(item.average_risk_score)}</span></div><Progress value={Number(item.average_risk_score) * 100} /></div>)}
          </CardContent></Card>
        </div></>}
      </DataState>
    </section>
  );
}
