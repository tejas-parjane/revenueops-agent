import { useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, errorMessage } from '../lib/api';
import { formatDateTime, titleCase } from '../lib/format';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  JsonView,
  Spinner,
  StatusBadge,
} from '../components/UI';
import type { AgentEvent, Task, TaskDetail } from '../types';

const DEFAULT_PROMPT = 'Find all high-value leads that haven\'t received a follow-up in 48 hours.';
const FINAL_STATUSES = ['completed', 'failed', 'cancelled', 'canceled', 'error'];

export default function AgentWorkspace() {
  const [searchParams, setSearchParams] = useSearchParams();
  const taskParam = searchParams.get('task');
  const [taskId, setTaskId] = useState<string | null>(taskParam);
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setTaskId(taskParam);
  }, [taskParam]);

  useEffect(() => {
    if (!taskId) {
      setTask(null);
      setEvents([]);
      return;
    }

    let active = true;
    setLoading(true);

    const load = async () => {
      try {
        const [detail, taskEvents] = await Promise.all([
          api.get<TaskDetail>(`/agent/tasks/${taskId}`),
          api.get<AgentEvent[]>(`/agent/tasks/${taskId}/events`),
        ]);
        if (!active) return;
        setTask(detail);
        setEvents(taskEvents.length ? taskEvents : detail.events ?? []);
        setError('');
        if (FINAL_STATUSES.includes(detail.status.toLowerCase())) {
          window.clearInterval(timer);
        }
      } catch (caught) {
        if (active) setError(errorMessage(caught));
      } finally {
        if (active) setLoading(false);
      }
    };

    const timer = window.setInterval(() => void load(), 1500);
    void load();

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [taskId]);

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim()) return;
    setLoading(true);
    setError('');
    try {
      const created = await api.post<Task>('/agent/tasks', { user_request: prompt.trim() });
      setTask(null);
      setEvents([]);
      setTaskId(created.id);
      setSearchParams({ task: created.id });
    } catch (caught) {
      setError(errorMessage(caught));
      setLoading(false);
    }
  }

  const running = task ? !FINAL_STATUSES.includes(task.status.toLowerCase()) : false;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title text-slate-900 dark:text-white">AI Agent</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Launch investigations and review the agent's evidence before approval.</p>
      </div>

      {error ? <ErrorBanner message={error} /> : null}

      <Card>
        <CardHeader title="New investigation" description="Describe the outcome you want the agent to analyze" />
        <form onSubmit={(event) => void createTask(event)} className="space-y-3 p-4">
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={3}
            className="input-field resize-y"
            aria-label="Agent request"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-slate-500 dark:text-slate-400">The agent proposes actions; it does not execute them without approval.</p>
            <Button type="submit" variant="primary" loading={loading && !task}>
              Run investigation
            </Button>
          </div>
        </form>
      </Card>

      {!taskId ? (
        <Card>
          <EmptyState title="No task selected" description="Run an investigation or open one from the pipeline to see its reasoning here." />
        </Card>
      ) : (
        <>
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="section-title">Task {taskId.slice(0, 8)}</p>
                  {task ? <StatusBadge status={task.status} /> : <Badge tone="sky">Loading</Badge>}
                  {running ? <Badge tone="violet">Live</Badge> : null}
                </div>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{task?.user_request ?? 'Retrieving task…'}</p>
              </div>
              <div className="text-right text-xs text-slate-500 dark:text-slate-400">
                <p>{task ? titleCase(task.task_type) : '—'}</p>
                <p className="mt-0.5">{task ? formatDateTime(task.created_at) : '—'}</p>
              </div>
            </div>

            {!task && loading ? (
              <div className="flex h-40 items-center justify-center text-slate-400"><Spinner /></div>
            ) : task ? (
              <div className="grid gap-4 p-4 lg:grid-cols-2">
                <div>
                  <p className="label-field">Intent</p>
                  <p className="text-sm text-slate-700 dark:text-slate-200">{task.intent || '—'}</p>
                </div>
                <div>
                  <p className="label-field">Completed</p>
                  <p className="text-sm text-slate-700 dark:text-slate-200">{formatDateTime(task.completed_at)}</p>
                </div>
                <div className="lg:col-span-2">
                  <p className="label-field">Reasoning summary</p>
                  <p className="whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm leading-6 text-slate-700 dark:bg-slate-950 dark:text-slate-300">
                    {task.reasoning_summary || 'Reasoning will appear once the agent has analyzed the data.'}
                  </p>
                </div>
                <div className="lg:col-span-2">
                  <p className="label-field">Data sources</p>
                  <JsonView value={task.data_sources ?? []} />
                </div>
                {task.result !== undefined ? (
                  <div className="lg:col-span-2">
                    <p className="label-field">Result</p>
                    <JsonView value={task.result} />
                  </div>
                ) : null}
                {task.error ? (
                  <div className="lg:col-span-2">
                    <ErrorBanner message={task.error} />
                  </div>
                ) : null}
              </div>
            ) : null}
          </Card>

          <div className="grid gap-5 xl:grid-cols-2">
            <Card>
              <CardHeader title="Agent timeline" description={`${events.length} events`} />
              {events.length ? (
                <div className="space-y-0 p-4">
                  {events.map((event, index) => (
                    <div key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
                      {index < events.length - 1 ? (
                        <span className="absolute left-[7px] top-4 h-full w-px bg-slate-200 dark:bg-slate-700" />
                      ) : null}
                      <span className="relative mt-1 h-3.5 w-3.5 shrink-0 rounded-full border-2 border-white bg-sky-500 ring-1 ring-sky-200 dark:border-slate-900 dark:ring-sky-500/40" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{event.step}</p>
                          <div className="flex items-center gap-2">
                            <StatusBadge status={event.status} />
                            <span className="text-[11px] text-slate-400">{formatDateTime(event.created_at)}</span>
                          </div>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-slate-600 dark:text-slate-400">{event.message}</p>
                        {event.metadata !== null && event.metadata !== undefined ? (
                          <JsonView value={event.metadata} className="mt-2 max-h-32" />
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No events yet" description="Agent steps will stream in as the task runs." />
              )}
            </Card>

            <div className="space-y-5">
              <Card>
                <CardHeader title="Findings" description={`${task?.findings?.length ?? 0} risk signals detected`} />
                {task?.findings?.length ? (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800">
                    {task.findings.map((finding) => (
                      <div key={finding.id} className="p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{finding.title}</p>
                          <StatusBadge status={finding.priority} />
                        </div>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{titleCase(finding.type)} · Lead {finding.lead_id.slice(0, 8)}</p>
                        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{finding.description}</p>
                        <JsonView value={finding.evidence} className="mt-2 max-h-32" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="No findings" description="Findings from the analysis will appear here." />
                )}
              </Card>

              <Card>
                <CardHeader title="Recommendations" description={`${task?.recommendations?.length ?? 0} proposed actions`} />
                {task?.recommendations?.length ? (
                  <div className="space-y-3 p-4">
                    {task.recommendations.map((recommendation) => (
                      <div key={recommendation.id} className="rounded-md border border-slate-200 p-3 dark:border-slate-800">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                            {recommendation.lead?.name ?? `Lead ${recommendation.lead_id.slice(0, 8)}`}
                          </p>
                          <div className="flex gap-1.5">
                            <StatusBadge status={recommendation.priority} />
                            <StatusBadge status={recommendation.status} />
                          </div>
                        </div>
                        <p className="mt-2 text-xs leading-5 text-slate-600 dark:text-slate-400">{recommendation.explanation}</p>
                        <p className="label-field mt-3">Proposed action</p>
                        <JsonView value={recommendation.proposed_action} className="max-h-40" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="No recommendations" description="Approved-ready actions will be listed here." />
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
