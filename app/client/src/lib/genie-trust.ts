export const executionDisclosure = 'Runs with your Databricks permissions';
export const answerDisclaimer = 'AI-generated — verify the answer against the generated SQL and source results.';

type QueryAttachment = { query?: { title?: string; description?: string; query?: string } };
type TrustMessage = { role: string; content?: string; attachments?: QueryAttachment[] };

export function collectGeneratedSql(messages: TrustMessage[]) {
  for (const message of [...messages].reverse()) {
    for (const attachment of message.attachments ?? []) {
      if (attachment.query?.query) return attachment.query;
    }
  }
  return null;
}

export function describeGenieState(status: string, messageCount: number, error: string | null) {
  if (status === 'error' || error) return 'error';
  if (status === 'streaming' || status.startsWith('loading')) return 'streaming';
  if (messageCount === 0) return 'empty';
  return 'ready';
}

export function isAmbiguousAnswer(message: TrustMessage | undefined) {
  return message?.role === 'assistant' && !message.content?.trim() && !message.attachments?.length;
}
