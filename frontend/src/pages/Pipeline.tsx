import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorMessage } from '../lib/api';
import { formatCurrency, formatDate, formatDateTime, relativeTime, titleCase } from '../lib/format';
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/UI';
import type { Lead } from '../types';

type SortKey = 'name' | 'company' | 'deal_value' | 'stage' | 'owner' | 'priority' | 'days_inactive' | 'last_activity_at';
type SortDirection = 'asc' | 'desc';

const columns: Array<{ key: SortKey; label: string }> = [
  { key: 'name', label: 'Lead' },
  { key: 'company', label: 'Company' },
  { key: 'deal_value', label: 'Value' },
  { key: 'stage', label: 'Stage' },
  { key: 'owner', label: 'Owner' },
  { key: 'priority', label: 'Priority' },
  { key: 'days_inactive', label: 'Inactive' },
  { key: 'last_activity_at', label: 'Last activity' },
];

function compareLeads(a: Lead, b: Lead, key: SortKey): number {
  const left = a[key];
  const right = b[key];
  if (typeof left === 'number' || typeof right === 'number') {
    return (Number(left ?? 0) - Number(right ?? 0));
  }
  return String(left ?? '').localeCompare(String(right ?? ''));
}

export default function Pipeline() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [stage, setStage] = useState('all');
  const [priority, setPriority] = useState('all');
  const [sortKey, setSortKey] = useState<SortKey>('deal_value');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [investigatingId, setInvestigatingId] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setLeads(await api.get<Lead[]>('/leads'));
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

  const stages = useMemo(() => Array.from(new Set(leads.map((lead) => lead.stage))).sort(), [leads]);
  const priorities = useMemo(
    () => Array.from(new Set(leads.map((lead) => lead.priority).filter((value): value is string => Boolean(value)))).sort(),
    [leads],
  );

  const visibleLeads = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return leads
      .filter((lead) => {
        const matchesQuery = !needle || [lead.name, lead.company, lead.owner].some((value) =>
          value?.toLowerCase().includes(needle),
        );
        return (
          matchesQuery &&
          (stage === 'all' || lead.stage === stage) &&
          (priority === 'all' || lead.priority === priority)
        );
      })
      .sort((a, b) => {
        const result = compareLeads(a, b, sortKey);
        return sortDirection === 'asc' ? result : -result;
      });
  }, [leads, query, stage, priority, sortKey, sortDirection]);

  const selectedLead = leads.find((lead) => lead.id === selectedId) ?? null;

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDirection('asc');
    }
  }

  async function investigateLead(lead: Lead) {
    setInvestigatingId(lead.id);
    setError('');
    try {
      const task = await api.post<{ id: string }>('/pipeline/investigate', {
        request: `Investigate ${lead.name}${lead.company ? ` at ${lead.company}` : ''} for follow-up risk and next best actions.`,
      });
      navigate(`/agent?task=${task.id}`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setInvestigatingId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title text-slate-900 dark:text-white">Pipeline</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Search, segment, and investigate revenue records.</p>
        </div>
        <Button onClick={() => void load()}>Refresh leads</Button>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void load()} /> : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="min-w-0">
          <div className="flex flex-wrap gap-2 border-b border-slate-200 p-3 dark:border-slate-800">
            <div className="min-w-[220px] flex-1">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search name, company, or owner…"
                className="input-field"
                aria-label="Search leads"
              />
            </div>
            <select value={stage} onChange={(event) => setStage(event.target.value)} className="input-field w-auto" aria-label="Filter by stage">
              <option value="all">All stages</option>
              {stages.map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
            </select>
            <select value={priority} onChange={(event) => setPriority(event.target.value)} className="input-field w-auto" aria-label="Filter by priority">
              <option value="all">All priorities</option>
              {priorities.map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
            </select>
          </div>

          {loading && !leads.length ? (
            <div className="flex h-64 items-center justify-center text-slate-400"><Spinner /></div>
          ) : visibleLeads.length ? (
            <Table>
              <TableHead>
                <TableRow>
                  {columns.map((column) => (
                    <TableHeader key={column.key}>
                      <button
                        type="button"
                        onClick={() => toggleSort(column.key)}
                        className="inline-flex items-center gap-1 hover:text-slate-800 dark:hover:text-slate-200"
                      >
                        {column.label}
                        <span className="text-[9px]">
                          {sortKey === column.key ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                        </span>
                      </button>
                    </TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {visibleLeads.map((lead) => (
                  <TableRow key={lead.id} onClick={() => setSelectedId(lead.id)}>
                    <TableCell className="font-medium text-slate-900 dark:text-slate-100">
                      <span className="block max-w-[180px] truncate">{lead.name}</span>
                      <span className="block text-xs font-normal text-slate-500">{lead.email ?? lead.external_id ?? '—'}</span>
                    </TableCell>
                    <TableCell className="max-w-[160px] truncate">{lead.company ?? '—'}</TableCell>
                    <TableCell className="font-medium tabular-nums">{formatCurrency(lead.deal_value)}</TableCell>
                    <TableCell><Badge>{titleCase(lead.stage)}</Badge></TableCell>
                    <TableCell>{lead.owner ?? '—'}</TableCell>
                    <TableCell><StatusBadge status={lead.priority} /></TableCell>
                    <TableCell className={lead.days_inactive !== null && lead.days_inactive > 7 ? 'text-rose-600 dark:text-rose-400' : ''}>
                      {lead.days_inactive === null ? '—' : `${lead.days_inactive}d`}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{relativeTime(lead.last_activity_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <EmptyState
              title={leads.length ? 'No matching leads' : 'No leads yet'}
              description={leads.length ? 'Adjust your search or filters.' : 'Connect an integration or import leads to get started.'}
            />
          )}
          <div className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
            {visibleLeads.length} of {leads.length} leads
          </div>
        </Card>

        <div className="xl:sticky xl:top-20 xl:self-start">
          <Card>
            <CardHeader title="Record detail" description={selectedLead ? selectedLead.name : 'Select a lead'} />
            {selectedLead ? (
              <div className="space-y-4 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={selectedLead.stage} />
                  <StatusBadge status={selectedLead.priority} />
                  {selectedLead.source_provider ? <Badge tone="violet">{titleCase(selectedLead.source_provider)}</Badge> : null}
                </div>

                <dl className="grid grid-cols-2 gap-x-3 gap-y-3 text-xs">
                  <div><dt className="text-slate-400">Company</dt><dd className="mt-0.5 font-medium text-slate-700 dark:text-slate-200">{selectedLead.company ?? '—'}</dd></div>
                  <div><dt className="text-slate-400">Owner</dt><dd className="mt-0.5 font-medium text-slate-700 dark:text-slate-200">{selectedLead.owner ?? '—'}</dd></div>
                  <div><dt className="text-slate-400">Value</dt><dd className="mt-0.5 font-medium text-slate-700 dark:text-slate-200">{formatCurrency(selectedLead.deal_value)}</dd></div>
                  <div><dt className="text-slate-400">Inactive</dt><dd className="mt-0.5 font-medium text-slate-700 dark:text-slate-200">{selectedLead.days_inactive === null ? '—' : `${selectedLead.days_inactive} days`}</dd></div>
                  <div><dt className="text-slate-400">Last activity</dt><dd className="mt-0.5 font-medium text-slate-700 dark:text-slate-200">{formatDateTime(selectedLead.last_activity_at)}</dd></div>
                  <div><dt className="text-slate-400">Created</dt><dd className="mt-0.5 font-medium text-slate-700 dark:text-slate-200">{formatDate(selectedLead.created_at)}</dd></div>
                </dl>

                <div>
                  <p className="label-field">Email</p>
                  <p className="truncate text-sm text-slate-700 dark:text-slate-200">{selectedLead.email ?? '—'}</p>
                </div>

                <div>
                  <p className="label-field">Notes</p>
                  <p className="whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-950 dark:text-slate-300">
                    {selectedLead.notes || 'No notes recorded.'}
                  </p>
                </div>

                <JsonView value={selectedLead} className="max-h-40" />

                <Button
                  variant="primary"
                  className="w-full"
                  loading={investigatingId === selectedLead.id}
                  onClick={() => void investigateLead(selectedLead)}
                >
                  Investigate lead
                </Button>
              </div>
            ) : (
              <EmptyState title="Select a record" description="Click a lead row to view its details and launch an investigation." />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
