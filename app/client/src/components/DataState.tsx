import type { ReactNode } from 'react';
import { Alert, AlertDescription, AlertTitle, Empty, EmptyDescription, EmptyHeader, EmptyTitle, Skeleton } from '@databricks/appkit-ui/react';
import { resolveDataState, type StateInput } from '../lib/workflow-state';

export function DataState({ loading, error, rows, stale, children }: StateInput & { children: ReactNode }) {
  const state = resolveDataState({ loading, error, rows, stale });
  if (state === 'loading') return <div className="space-y-3" aria-label="Loading data"><Skeleton className="h-24" /><Skeleton className="h-48" /></div>;
  if (state === 'error') return <Alert variant="destructive"><AlertTitle>Data unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>;
  if (state === 'empty') return <Empty><EmptyHeader><EmptyTitle>No results</EmptyTitle><EmptyDescription>Adjust filters or check your assigned caseload.</EmptyDescription></EmptyHeader></Empty>;
  return <>{stale && <Alert><AlertTitle>Partial or stale data</AlertTitle><AlertDescription>The latest successful refresh is shown. Confirm freshness before acting.</AlertDescription></Alert>}{children}</>;
}
