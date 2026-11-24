import { useCallback, useEffect, useState } from 'react';
import { api, errorMessage } from '../lib/api';
import { formatDateTime, relativeTime, titleCase } from '../lib/format';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Spinner,
  StatusBadge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/UI';
import type { ActivityItem, Execution } from '../types';

function isFailed(status: string): boolean {
  const value = status.toLowerCase();
  return value.includes('fail') || value.includes('error') || value === 'rejected';
}

export default function Activity() {
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [items, runs] = await Promise.all([
        api.get<ActivityItem[]>('/dashboard/activity'),
        api.get<Execution[]>('/executions'),
      ]);
      setActivity(items);
      setExecutions(runs);
      setError('');
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function retry(execution: Execution) {
    setRetryingId(execution.id);
    setError('');
    try {
      await api.post(`/executions/${execution.id}/retry`);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setRetryingId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title text-slate-900 dark:text-white">Activity</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Trace agent tasks, executed actions, and integration outcomes.</p>
        </div>
        <Button onClick={() => void load()}>Refresh</Button>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void load()} /> : null}

      {loading && !activity.length && !executions.length ? (
        <div className="flex h-64 items-center justify-center text-slate-400"><Spinner /></div>
      ) : (
        <>
          <Card>
            <CardHeader title="Workspace activity" description={`${activity.length} events`} />
            {activity.length ? (
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeader>Event</TableHeader>
                    <TableHeader>Type</TableHeader>
                    <TableHeader>Initiator</TableHeader>
                    <TableHeader>Provider</TableHeader>
                    <TableHeader>Status</TableHeader>
                    <TableHeader>Timestamp</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {activity.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="max-w-[320px]">
                        <p className="font-medium text-slate-900 dark:text-slate-100">{item.title}</p>
                        {item.detail ? (
                          <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">{JSON.stringify(item.detail)}</p>
                        ) : null}
                      </TableCell>
                      <TableCell><Badge>{titleCase(item.type)}</Badge></TableCell>
                      <TableCell>{item.actor}</TableCell>
                      <TableCell>{item.provider ? titleCase(item.provider) : '—'}</TableCell>
                      <TableCell><StatusBadge status={item.status} /></TableCell>
                      <TableCell className="whitespace-nowrap" title={formatDateTime(item.timestamp)}>{relativeTime(item.timestamp)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState title="No activity recorded" />
            )}
          </Card>

          <Card>
            <CardHeader title="Action executions" description={`${executions.length} executions`} />
            {executions.length ? (
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeader>Action</TableHeader>
                    <TableHeader>Task</TableHeader>
                    <TableHeader>Integration</TableHeader>
                    <TableHeader>Idempotency key</TableHeader>
                    <TableHeader>Executed</TableHeader>
                    <TableHeader>Status</TableHeader>
                    <TableHeader>Error</TableHeader>
                    <TableHeader />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {executions.map((execution) => (
                    <TableRow key={execution.id}>
                      <TableCell className="font-medium text-slate-900 dark:text-slate-100">{titleCase(execution.action_type)}</TableCell>
                      <TableCell className="font-mono text-xs">{execution.task_id?.slice(0, 8) ?? '—'}</TableCell>
                      <TableCell className="font-mono text-xs">{execution.integration_id?.slice(0, 8) ?? '—'}</TableCell>
                      <TableCell className="max-w-[160px] truncate font-mono text-xs">{execution.idempotency_key}</TableCell>
                      <TableCell className="whitespace-nowrap">{formatDateTime(execution.executed_at)}</TableCell>
                      <TableCell><StatusBadge status={execution.status} /></TableCell>
                      <TableCell className="max-w-[240px]">
                        {execution.error_message ? (
                          <span className="text-xs text-rose-600 dark:text-rose-400">{execution.error_message}</span>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {isFailed(execution.status) ? (
                          <Button
                            size="sm"
                            loading={retryingId === execution.id}
                            onClick={() => void retry(execution)}
                          >
                            Retry
                          </Button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState title="No executions yet" description="Approved actions will show up here with their outcomes." />
            )}
          </Card>
        </>
      )}
    </div>
  );
}
