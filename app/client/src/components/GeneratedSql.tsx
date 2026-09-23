import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@databricks/appkit-ui/react';

export function GeneratedSql({ sql }: { sql: { title?: string; description?: string; query?: string } | null }) {
  if (!sql?.query) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Generated SQL</CardTitle>
        <CardDescription>{sql.title ?? sql.description ?? 'How the latest answer was computed'}</CardDescription>
      </CardHeader>
      <CardContent>
        <pre className="max-h-72 overflow-auto rounded-md bg-muted p-4 text-xs">
          <code>{sql.query}</code>
        </pre>
      </CardContent>
    </Card>
  );
}
