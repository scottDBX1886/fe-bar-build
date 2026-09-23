import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@databricks/appkit-ui/react';

export function AdvisorCaseloadPage() {
  return (
    <section className="mx-auto max-w-7xl space-y-6" aria-labelledby="caseload-heading">
      <div>
        <p className="text-sm font-medium text-muted-foreground">Operational workflow</p>
        <h2 id="caseload-heading" className="text-3xl font-semibold tracking-tight text-foreground">
          Advisor Caseload
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Advisor-scoped students and intervention actions will appear here in Task 12.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Lakebase operational path ready</CardTitle>
          <CardDescription>
            Serving reads and intervention write-back use distinct Postgres tables to prevent synchronization overwrite
            loops.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Student access remains governed by advisor identity; protected demographic attributes are not exposed.
        </CardContent>
      </Card>
    </section>
  );
}
