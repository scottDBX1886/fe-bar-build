import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@databricks/appkit-ui/react';

export function ExecutiveOverviewPage() {
  return (
    <section className="mx-auto max-w-7xl space-y-6" aria-labelledby="executive-heading">
      <div>
        <p className="text-sm font-medium text-muted-foreground">Student retention</p>
        <h2 id="executive-heading" className="text-3xl font-semibold tracking-tight text-foreground">
          Executive Overview
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Governed aggregate metrics will appear here in Task 12. Analytics queries run through the selected SQL
          warehouse.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Decision-support shell ready</CardTitle>
          <CardDescription>
            Aggregate retention, intervention coverage, and synthetic tuition exposure will remain separated from
            student-level access.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Source: Unity Catalog Gold · Freshness and reporting period will be displayed with every metric.
        </CardContent>
      </Card>
    </section>
  );
}
