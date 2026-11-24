import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorMessage } from '../lib/api';
import { formatCurrency, formatNumber, relativeTime, titleCase } from '../lib/format';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  MetricCard,
  Spinner,
  StatusBadge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/UI';
import type { DashboardOverview, Lead } from '../types';

function LeadTable({ leads, showInactivity = false }: { leads: Lead[]; showInactivity?: boolean }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Record</TableHeader>
          <TableHeader>Stage</TableHeader>
          <TableHeader>Value</TableHeader>
          {showInactivity ? <TableHeader>Inactive</TableHeader> : null}
          <TableHeader>Priority</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {leads.map((lead) => (
          <TableRow key={lead.id}>
            <TableCell>
              <p className="font-medium text-slate-900 dark:text-slate-100">{lead.name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{lead.company ?? lead.email ?? 'No company'}</p>
            </TableCell>
            <TableCell><Badge>{titleCase(lead.stage)}</Badge></TableCell>
            <TableCell className="font-medium tabular-nums">{formatCurrency(lead.deal_value)}</TableCell>
            {showInactivity ? (
              <TableCell>
                <span className={lead.days_inactive !== null && lead.days_inactive > 7 ? 'text-rose-600 dark:text-rose-400' : ''}>
                  {lead.days_inactive === null ? '—' : `${lead.days_inactive}d`}
                </span>
              </TableCell>
            ) : null}
            <TableCell><StatusBadge status={lead.priority} /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default function Overview() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [investigating, setInvestigating] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setOverview(await api.get<DashboardOverview>('/dashboard/overview'));
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

  async function investigate() {
    setInvestigating(true);
    try {
      const task = await api.post<{ id: string }>('/agent/tasks', {
        user_request: 'Investigate the pipeline and identify high-value opportunities at risk of slipping.',
      });
      navigate(`/agent?task=${task.id}`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setInvestigating(false);
    }
  }

  if (loading && !overview) {
    return <div className="flex h-64 items-center justify-center text-slate-400"><Spinner /></div>;
  }

  const metrics = overview?.metrics;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title text-slate-900 dark:text-white">Overview</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Live signal across your revenue operation.</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => void load()}>Refresh</Button>
          <Button variant="primary" loading={investigating} onClick={() => void investigate()}>
            Investigate pipeline
          </Button>
        </div>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void load()} /> : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-6">
        <MetricCard label="Active leads" value={metrics ? formatNumber(metrics.active_leads) : '—'} tone="sky" hint="In open stages" />
        <MetricCard label="Pipeline value" value={metrics ? formatCurrency(metrics.pipeline_value) : '—'} tone="emerald" hint="Open deal value" />
        <MetricCard label="Neglected" value={metrics ? formatNumber(metrics.neglected_leads) : '—'} tone="amber" hint="No recent activity" />
        <MetricCard label="Overdue follow-ups" value={metrics ? formatNumber(metrics.overdue_followups) : '—'} tone="rose" hint="Past due date" />
        <MetricCard label="Pending approvals" value={metrics ? formatNumber(metrics.pending_approvals) : '—'} tone="violet" hint="Awaiting review" />
        <MetricCard label="Completed tasks" value={metrics ? formatNumber(metrics.completed_tasks) : '—'} tone="sky" hint="Agent runs finished" />
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Needs attention"
            description="Records with elevated risk signals"
            action={<Badge tone="amber">{overview?.needs_attention.length ?? 0} records</Badge>}
          />
          {overview?.needs_attention.length ? (
            <LeadTable leads={overview.needs_attention} showInactivity />
          ) : (
            <EmptyState title="No records need attention" description="Risk monitors have not flagged any leads." />
          )}
        </Card>

        <Card>
          <CardHeader title="Recent activity" description="Latest workspace events" />
          {overview?.recent_activity.length ? (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {overview.recent_activity.map((item) => (
                <div key={item.id} className="px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{item.title}</p>
                    <StatusBadge status={item.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {titleCase(item.type)} · {item.actor} · {relativeTime(item.timestamp)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No activity yet" />
          )}
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="High-priority opportunities" description="Largest open deals to protect" />
          {overview?.high_priority.length ? (
            <LeadTable leads={overview.high_priority} />
          ) : (
            <EmptyState title="No high-priority opportunities" />
          )}
        </Card>

        <Card>
          <CardHeader title="Integration health" description="Connected data sources" />
          {overview?.integration_health.length ? (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {overview.integration_health.map((integration) => (
                <div key={integration.id} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{titleCase(integration.provider)}</p>
                    <StatusBadge status={integration.connection_status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Last sync {relativeTime(integration.last_synced_at)}
                  </p>
                  {integration.last_error ? (
                    <p className="mt-1 truncate text-xs text-rose-600 dark:text-rose-400">{integration.last_error}</p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No integrations connected" description="Connect a source from the Integrations page." />
          )}
        </Card>
      </div>
    </div>
  );
}
