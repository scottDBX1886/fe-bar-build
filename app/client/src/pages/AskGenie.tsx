import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  GenieChatInput,
  GenieChatMessage,
  Spinner,
  useGenieChat,
} from '@databricks/appkit-ui/react';
import { GeneratedSql } from '../components/GeneratedSql';
import {
  answerDisclaimer,
  collectGeneratedSql,
  describeGenieState,
  executionDisclosure,
  isAmbiguousAnswer,
} from '../lib/genie-trust';
import { fetchWhoAmI, type WhoAmI } from '../lib/whoami';

const examples = [
  'Which programs have the highest current retention risk?',
  'How has intervention coverage changed by score date?',
  'Summarize estimated next-term tuition exposure by program.',
];

export function AskGenie() {
  const chat = useGenieChat({ alias: 'default' });
  const [identity, setIdentity] = useState<WhoAmI | null>(null);
  useEffect(() => {
    void fetchWhoAmI()
      .then(setIdentity)
      .catch(() => setIdentity(null));
  }, []);
  const generatedSql = useMemo(() => collectGeneratedSql(chat.messages), [chat.messages]);
  const state = describeGenieState(chat.status, chat.messages.length, chat.error);
  const latest = chat.messages.at(-1);
  const ambiguous = isAmbiguousAnswer(latest);
  return (
    <section className="mx-auto max-w-7xl space-y-6" aria-labelledby="genie-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Governed natural-language analytics</p>
          <h2 id="genie-heading" className="text-3xl font-semibold">
            Ask Genie
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Ask retention questions against the curated Student Retention Advisor space.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Badge variant="secondary">{identity?.email ?? identity?.user ?? 'Signed in'}</Badge>
          <span className="text-xs text-muted-foreground">{executionDisclosure}</span>
        </div>
      </div>
      <Alert>
        <AlertTitle>Governed AI analysis</AlertTitle>
        <AlertDescription>
          Genie executes on behalf of you. Results are limited by your Unity Catalog permissions and the curated space.
        </AlertDescription>
      </Alert>
      {state === 'error' && (
        <Alert variant="destructive">
          <AlertTitle>Genie could not answer</AlertTitle>
          <AlertDescription>{chat.error ?? 'Rephrase the question or start a new conversation.'}</AlertDescription>
        </Alert>
      )}
      {ambiguous && (
        <Alert>
          <AlertTitle>Clarification needed</AlertTitle>
          <AlertDescription>
            Genie did not return a clear answer. Add a program, term, cohort, or score-date constraint and retry.
          </AlertDescription>
        </Alert>
      )}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <Card className="min-h-[680px]">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Student Retention Advisor</CardTitle>
              <CardDescription>Conversation and result attachments</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={chat.reset}>
              New conversation
            </Button>
          </CardHeader>
          <CardContent className="flex h-[590px] flex-col gap-4">
            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-2" aria-live="polite">
              {state === 'empty' ? (
                <Empty>
                  <EmptyHeader>
                    <EmptyTitle>Ask a retention question</EmptyTitle>
                    <EmptyDescription>
                      Be specific about the program, cohort, term, measure, or score date.
                    </EmptyDescription>
                  </EmptyHeader>
                  <EmptyContent className="flex flex-col gap-2">
                    {examples.map((example) => (
                      <Button variant="outline" key={example} onClick={() => chat.sendMessage(example)}>
                        {example}
                      </Button>
                    ))}
                  </EmptyContent>
                </Empty>
              ) : (
                chat.messages.map((message) => (
                  <div key={message.id} className="space-y-2">
                    <GenieChatMessage message={message} />
                    {message.role === 'assistant' && (
                      <p className="px-3 text-xs text-muted-foreground">{answerDisclaimer}</p>
                    )}
                  </div>
                ))
              )}
              {state === 'streaming' && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner /> Analyzing your governed data…
                </div>
              )}
            </div>
            <GenieChatInput
              onSend={chat.sendMessage}
              disabled={state === 'streaming'}
              placeholder="Ask about student retention"
            />
            <p className="text-xs text-muted-foreground">{answerDisclaimer}</p>
          </CardContent>
        </Card>
        <aside className="space-y-4">
          <GeneratedSql sql={generatedSql} />
          <Card>
            <CardHeader>
              <CardTitle>Trust checklist</CardTitle>
              <CardDescription>Review before using an answer</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>Identity: {identity?.email ?? identity?.user ?? 'Signed-in Databricks user'}</p>
              <p>Execution: on behalf of your user permissions</p>
              <p>Sources: inspect query and result attachments in each answer</p>
              <p>Verification: compare claims to generated SQL and governed results</p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </section>
  );
}
