import { useState } from 'react';
import {
  Alert,
  AlertDescription,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@databricks/appkit-ui/react';
import { submitIntervention } from '../../lib/workflows';

export function InterventionWorkflow({
  studentId,
  advisorId,
  onSaved,
}: {
  studentId: string;
  advisorId: string;
  onSaved: () => void;
}) {
  const [type, setType] = useState('outreach');
  const [priority, setPriority] = useState('high');
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const response = await submitIntervention({
        interventionId: crypto.randomUUID(),
        studentId,
        advisorId,
        interventionType: type,
        priority,
        idempotencyKey: crypto.randomUUID(),
      });
      setMessage(response.status === 'replayed' ? 'This action was already recorded.' : 'Intervention created.');
      onSaved();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Unable to save');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>Create intervention</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm">
          Type
          <Select value={type} onValueChange={setType}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="outreach">Outreach</SelectItem>
              <SelectItem value="academic_support">Academic support</SelectItem>
              <SelectItem value="financial_support">Financial support</SelectItem>
              <SelectItem value="case_review">Case review</SelectItem>
            </SelectContent>
          </Select>
        </label>
        <label className="grid gap-1 text-sm">
          Priority
          <Select value={priority} onValueChange={setPriority}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="urgent">Urgent</SelectItem>
            </SelectContent>
          </Select>
        </label>
        <Input type="hidden" value={studentId} readOnly />
        <Button
          disabled={busy}
          onClick={() => {
            void submit();
          }}
        >
          {busy ? 'Saving…' : 'Create'}
        </Button>
        {message && (
          <Alert className="basis-full">
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
