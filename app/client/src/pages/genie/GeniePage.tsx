import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@databricks/appkit-ui/react';

export function GeniePage() {
  return (
    <section className="mx-auto max-w-5xl space-y-6" aria-labelledby="genie-heading">
      <div>
        <p className="text-sm font-medium text-muted-foreground">Governed natural-language analytics</p>
        <h2 id="genie-heading" className="text-3xl font-semibold tracking-tight text-foreground">
          Ask Genie
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          The curated Student Retention Advisor space is attached. Task 13 adds the trusted embedded conversation
          experience.
        </p>
      </div>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Student Retention Advisor</CardTitle>
              <CardDescription>Curated against approved Unity Catalog Gold sources.</CardDescription>
            </div>
            <Badge variant="secondary">Runs with your Databricks permissions</Badge>
          </div>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          The deployed app requests the dashboards.genie user scope, so Genie executes on behalf of the signed-in user.
          Generated SQL, sources, streaming state, and an AI verification notice will be visible in Task 13.
        </CardContent>
      </Card>
    </section>
  );
}
