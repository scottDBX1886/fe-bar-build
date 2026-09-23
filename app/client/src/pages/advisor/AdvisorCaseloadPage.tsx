import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { sql } from '@databricks/appkit-ui/js';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  useAnalyticsQuery,
} from '@databricks/appkit-ui/react';
import { DataState } from '../../components/DataState';
import type { CaseloadRow } from '../../lib/workflows';
import { sortCaseload } from '../../lib/workflow-state';

const text = (value: unknown) => (typeof value === 'string' ? value : '');

export function AdvisorCaseloadPage() {
  const [page, setPage] = useState(1);
  const [riskTier, setRiskTier] = useState('all');
  const params = useMemo(
    () => ({
      riskTier: sql.string(riskTier === 'all' ? '' : riskTier),
      pageSize: sql.int(25),
      pageOffset: sql.int((page - 1) * 25),
    }),
    [page, riskTier]
  );
  const query = useAnalyticsQuery('advisor_caseload', params);
  const rows: CaseloadRow[] = (query.data ?? []).map((row) => ({
    student_id: text(row.student_id),
    advisor_id: text(row.advisor_id),
    program_code: text(row.program_code),
    risk_score: Number(row.risk_score),
    risk_tier: text(row.risk_tier),
    intervention_status: text(row.intervention_status),
    caseload_priority: Number(row.caseload_priority),
    follow_up_due: Boolean(row.follow_up_due),
    leading_factors: [],
  }));
  const total = Number(query.data?.[0]?.total_count ?? 0);
  const sorted = sortCaseload(rows);
  return (
    <section className="mx-auto max-w-7xl space-y-6" aria-labelledby="caseload-heading">
      <div>
        <p className="text-sm font-medium text-muted-foreground">Operational workflow</p>
        <h2 id="caseload-heading" className="text-3xl font-semibold">
          Advisor Caseload
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Your governed assignments, ordered by actionable risk and follow-up urgency.
        </p>
      </div>
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Assigned students</CardTitle>
            <CardDescription>{total} students · warehouse-filtered and paginated</CardDescription>
          </div>
          <Select
            value={riskTier}
            onValueChange={(value) => {
              setRiskTier(value);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All risk tiers</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          <DataState loading={query.loading} error={query.error} rows={sorted.length}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Program</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Follow-up</TableHead>
                  <TableHead>Intervention</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((row) => (
                  <TableRow key={row.student_id}>
                    <TableCell>
                      <Link className="font-medium underline" to={`/students/${row.student_id}`}>
                        {row.student_id}
                      </Link>
                    </TableCell>
                    <TableCell>{row.program_code}</TableCell>
                    <TableCell>
                      <Badge variant={row.risk_tier === 'critical' ? 'destructive' : 'secondary'}>
                        {row.risk_tier} · {(row.risk_score * 100).toFixed(0)}%
                      </Badge>
                    </TableCell>
                    <TableCell>{row.follow_up_due ? 'Due now' : 'Not due'}</TableCell>
                    <TableCell>{row.intervention_status}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button variant="outline" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <span className="text-sm">Page {page}</span>
              <Button variant="outline" disabled={page * 25 >= total} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </DataState>
        </CardContent>
      </Card>
    </section>
  );
}
