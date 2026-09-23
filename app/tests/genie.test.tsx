import { describe, expect, it } from 'vitest';
import { answerDisclaimer, collectGeneratedSql, describeGenieState, executionDisclosure } from '../client/src/lib/genie-trust';

describe('trusted embedded Genie', () => {
  it('discloses on-behalf-of-user execution', () => {
    expect(executionDisclosure).toContain('your Databricks permissions');
  });

  it('extracts generated SQL and its source attachment', () => {
    const sql = collectGeneratedSql([{ role: 'assistant', attachments: [{ query: { title: 'Risk by program', query: 'SELECT program_code, count(*) FROM gold GROUP BY 1' } }] }]);
    expect(sql).toMatchObject({ title: 'Risk by program' });
    expect(sql?.query).toContain('SELECT');
  });

  it.each([
    ['streaming', 1, null, 'streaming'],
    ['error', 1, 'failed', 'error'],
    ['idle', 0, null, 'empty'],
    ['idle', 1, null, 'ready'],
  ] as const)('maps %s status to a visible %s state', (status, messages, error, expected) => {
    expect(describeGenieState(status, messages, error)).toBe(expected);
  });

  it('requires verification on every AI answer', () => {
    expect(answerDisclaimer).toMatch(/AI-generated.*verify/i);
  });
});
