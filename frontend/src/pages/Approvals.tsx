import { useCallback, useEffect, useState } from 'react';
import { api, errorMessage } from '../lib/api';
import { formatDateTime, titleCase } from '../lib/format';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  JsonView,
  Spinner,
  StatusBadge,
} from '../components/UI';
import type { ApprovalDetail, Execution } from '../types';

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function actionOf(approval: ApprovalDetail): Record<string, unknown> {
  return asRecord(approval.recommendation?.proposed_action);
}

function actionTypeOf(approval: ApprovalDetail): string {
  const action = actionOf(approval);
  const value = stringValue(action.type) ?? stringValue(action.action_type);
  return value ? titleCase(value) : 'Proposed Action';
}

function isPending(status: string): boolean {
  const value = status.toLowerCase();
  return value === 'pending' || value === 'awaiting_approval' || value === 'needs_review' || value === 'review';
}

export default function Approvals() {
  const [approvals, setApprovals] = useState<ApprovalDetail[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedJson, setEditedJson] = useState('{}');
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [items, runs] = await Promise.all([
        api.get<ApprovalDetail[]>('/approvals'),
        api.get<Execution[]>('/executions'),
      ]);
      setApprovals(items);
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

  function startEdit(approval: ApprovalDetail) {
    setActionError('');
    setRejectingId(null);
    setEditingId(approval.id);
    setEditedJson(JSON.stringify(approval.recommendation.proposed_action ?? {}, null, 2));
  }

  function startReject(approval: ApprovalDetail) {
    setActionError('');
    setEditingId(null);
    setRejectingId(approval.id);
    setRejectReason('');
  }

  async function approve(approval: ApprovalDetail, edited: boolean) {
    setActionError('');
    let editedPayload: Record<string, unknown> | null = null;

    if (edited) {
      try {
        const parsed: unknown = JSON.parse(editedJson);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          throw new Error('Edited payload must be a JSON object.');
        }
        editedPayload = parsed as Record<string, unknown>;
      } catch (caught) {
        setActionError(errorMessage(caught));
        return;
      }
    }

    setBusyId(approval.id);
    try {
      await api.post(`/approvals/${approval.id}/approve`, {
        edited_payload: editedPayload,
        expected_hash: approval.action_hash,
        note: null,
      });
      setEditingId(null);
      await load();
    } catch (caught) {
      setActionError(errorMessage(caught));
    } finally {
      setBusyId(null);
    }
  }

  async function reject(approval: ApprovalDetail) {
    setActionError('');
    setBusyId(approval.id);
    try {
      await api.post(`/approvals/${approval.id}/reject`, { reason: rejectReason || undefined });
      setRejectingId(null);
      setRejectReason('');
      await load();
    } catch (caught) {
      setActionError(errorMessage(caught));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title text-slate-900 dark:text-white">Approvals</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Review proposed actions before anything reaches a connected system.</p>
        </div>
        <Button onClick={() => void load()}>Refresh approvals</Button>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void load()} /> : null}
      {actionError ? <ErrorBanner message={actionError} /> : null}

      {loading && !approvals.length ? (
        <div className="flex h-64 items-center justify-center text-slate-400"><Spinner /></div>
      ) : approvals.length ? (
        <div className="grid gap-4 2xl:grid-cols-2">
          {approvals.map((approval) => {
            const canAct = isPending(approval.status);
            const lead = approval.lead;
            const recommendation = approval.recommendation;
            const action = actionOf(approval);
            const provider = stringValue(action.provider);
            const execution = executions.find(
              (item) => item.recommendation_id === approval.recommendation_id,
            );

            return (
              <Card key={approval.id} className="overflow-hidden">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="section-title">{actionTypeOf(approval)}</p>
                      <StatusBadge status={approval.status} />
                      <Badge tone={approval.risk_level.toLowerCase() === 'low' ? 'emerald' : approval.risk_level.toLowerCase() === 'high' ? 'rose' : 'amber'}>
                        {titleCase(approval.risk_level)} risk
                      </Badge>
                      {provider ? <Badge tone="sky">{titleCase(provider)}</Badge> : null}
                    </div>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      Created {formatDateTime(recommendation.created_at)} · Expires {formatDateTime(approval.expires_at)}
                    </p>
                  </div>
                  <span className="font-mono text-[10px] text-slate-400">{approval.id.slice(0, 8)}</span>
                </div>

                <div className="space-y-4 p-4">
                  <div className="rounded-md border border-slate-200 p-3 dark:border-slate-800">
                    <p className="label-field">Affected record</p>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{lead.name}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {lead.company ?? 'No company'} · {titleCase(lead.stage)} · ${lead.deal_value.toLocaleString()}
                        </p>
                        {lead.email ? (
                          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{lead.email}</p>
                        ) : null}
                      </div>
                      <StatusBadge status={lead.priority} />
                    </div>
                  </div>

                  <div>
                    <p className="label-field">Business justification</p>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-slate-600 dark:text-slate-300">
                      {recommendation.explanation || 'No justification supplied.'}
                    </p>
                  </div>

                  <div>
                    <p className="label-field">Proposed changes</p>
                    <JsonView value={recommendation.proposed_action} />
                  </div>

                  {recommendation.evidence.length ? (
                    <div>
                      <p className="label-field">Supporting evidence</p>
                      <JsonView value={recommendation.evidence} className="max-h-32" />
                    </div>
                  ) : null}

                  <div className="text-[11px] text-slate-400">
                    Action hash <span className="font-mono">{approval.action_hash.slice(0, 24)}…</span>
                    {approval.approved_by ? ` · Approved by ${approval.approved_by}` : ''}
                    {approval.note ? ` · Note: ${approval.note}` : ''}
                  </div>

                  {execution ? (
                    <div className="rounded-md border border-slate-200 p-3 dark:border-slate-800">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="label-field">Execution result</p>
                        <StatusBadge status={execution.status} />
                      </div>
                      <p className="mt-1 font-mono text-[10px] text-slate-400">
                        Idempotency key {execution.idempotency_key}
                      </p>
                      {execution.error_message ? (
                        <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">{execution.error_message}</p>
                      ) : null}
                      {execution.response_payload ? (
                        <JsonView value={execution.response_payload} className="mt-2 max-h-32" />
                      ) : null}
                    </div>
                  ) : null}

                  {editingId === approval.id ? (
                    <div>
                      <label className="label-field" htmlFor={`edit-${approval.id}`}>Edit proposed payload (JSON)</label>
                      <textarea
                        id={`edit-${approval.id}`}
                        value={editedJson}
                        onChange={(event) => setEditedJson(event.target.value)}
                        rows={8}
                        spellCheck={false}
                        className="input-field font-mono text-xs"
                      />
                    </div>
                  ) : null}

                  {rejectingId === approval.id ? (
                    <div>
                      <label className="label-field" htmlFor={`reject-${approval.id}`}>Rejection reason</label>
                      <textarea
                        id={`reject-${approval.id}`}
                        value={rejectReason}
                        onChange={(event) => setRejectReason(event.target.value)}
                        rows={3}
                        placeholder="Explain why this action should not run"
                        className="input-field"
                      />
                    </div>
                  ) : null}

                  <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
                    <Button variant="primary" size="sm" disabled={!canAct} loading={busyId === approval.id} onClick={() => void approve(approval, false)}>
                      Approve
                    </Button>
                    <Button size="sm" disabled={!canAct} loading={busyId === approval.id && editingId === approval.id} onClick={() => startEdit(approval)}>
                      Edit &amp; Approve
                    </Button>
                    <Button variant="danger" size="sm" disabled={!canAct} loading={busyId === approval.id && rejectingId === approval.id} onClick={() => startReject(approval)}>
                      Reject
                    </Button>
                    {editingId === approval.id ? (
                      <>
                        <Button variant="primary" size="sm" loading={busyId === approval.id} onClick={() => void approve(approval, true)}>
                          Save &amp; approve
                        </Button>
                        <Button size="sm" onClick={() => setEditingId(null)}>Cancel</Button>
                      </>
                    ) : null}
                    {rejectingId === approval.id ? (
                      <>
                        <Button variant="danger" size="sm" loading={busyId === approval.id} onClick={() => void reject(approval)}>
                          Confirm rejection
                        </Button>
                        <Button size="sm" onClick={() => setRejectingId(null)}>Cancel</Button>
                      </>
                    ) : null}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card><EmptyState title="No approvals pending" description="Agent-proposed actions will appear here for your review." /></Card>
      )}
    </div>
  );
}
