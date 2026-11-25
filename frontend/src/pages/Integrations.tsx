import { useCallback, useEffect, useState } from 'react';
import { api, errorMessage } from '../lib/api';
import { relativeTime, titleCase } from '../lib/format';
import { Badge, Button, Card, EmptyState, ErrorBanner, Spinner, StatusBadge } from '../components/UI';
import type { Integration, IntegrationConnectResponse } from '../types';

const providers = [
  { key: 'hubspot', name: 'HubSpot', description: 'CRM contacts, deals, and pipeline stages', initial: 'H', color: 'bg-orange-500' },
  { key: 'gmail', name: 'Gmail', description: 'Email threads and follow-up signals', initial: 'M', color: 'bg-rose-500' },
  { key: 'google_sheets', name: 'Google Sheets', description: 'Spreadsheet imports and exports', initial: 'S', color: 'bg-emerald-500' },
] as const;

function statusMessage(integration: Integration | undefined): string | null {
  if (!integration) return null;
  const status = integration.connection_status.toLowerCase();
  if (status === 'expired') {
    return integration.last_error || 'OAuth credentials expired. Reconnect this provider.';
  }
  if (status === 'disconnected') {
    return 'This provider is disconnected. Reconnect to resume syncing.';
  }
  if (status === 'error') {
    return integration.last_error || 'The last sync failed. Retry or reconnect this provider.';
  }
  return integration.last_error;
}

export default function Integrations() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setIntegrations(await api.get<Integration[]>('/integrations'));
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

  async function connect(providerKey: string) {
    setBusyKey(`connect:${providerKey}`);
    setError('');
    try {
      const connection = await api.get<IntegrationConnectResponse>(`/integrations/${providerKey}/connect`);
      if (connection.mode === 'live') {
        window.location.assign(connection.authorization_url);
        return;
      }
      const externalAccountId = `mock-${providerKey}-${Date.now()}`;
      const query = new URLSearchParams({
        state: connection.state,
        external_account_id: externalAccountId,
      });
      await api.get<Integration>(`/integrations/${providerKey}/callback?${query.toString()}`);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusyKey(null);
    }
  }

  async function sync(integration: Integration) {
    setBusyKey(`sync:${integration.id}`);
    setError('');
    try {
      await api.post(`/integrations/${integration.id}/sync`);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusyKey(null);
    }
  }

  async function disconnect(integration: Integration) {
    setBusyKey(`disconnect:${integration.id}`);
    setError('');
    try {
      await api.del(`/integrations/${integration.id}`);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title text-slate-900 dark:text-white">Integrations</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Connect data sources and keep revenue signals in sync.</p>
        </div>
        <Button onClick={() => void load()}>Refresh status</Button>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void load()} /> : null}

      {loading && !integrations.length ? (
        <div className="flex h-64 items-center justify-center text-slate-400"><Spinner /></div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {providers.map((provider) => {
            const matches = integrations.filter(
              (integration) => integration.provider.toLowerCase().replace(/[\s-]+/g, '_') === provider.key,
            );
            const integration = matches[0];
            const connected = Boolean(integration && ['connected', 'active', 'healthy'].includes(integration.connection_status.toLowerCase()));

            return (
              <Card key={provider.key} className="flex h-full flex-col">
                <div className="flex items-start gap-3 border-b border-slate-200 p-4 dark:border-slate-800">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white ${provider.color}`}>
                    {provider.initial}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="section-title">{provider.name}</p>
                      <StatusBadge status={integration?.connection_status ?? 'disconnected'} />
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">{provider.description}</p>
                  </div>
                </div>

                <div className="flex-1 space-y-3 p-4 text-xs">
                  <div className="flex justify-between gap-3">
                    <span className="text-slate-400">Last sync</span>
                    <span className="text-right font-medium text-slate-600 dark:text-slate-300">
                      {integration ? relativeTime(integration.last_synced_at) : 'Never'}
                    </span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span className="text-slate-400">Mode</span>
                    <Badge tone={integration?.mode === 'live' ? 'emerald' : 'neutral'}>
                      {integration?.mode === 'live' ? 'Live OAuth' : 'Mock data'}
                    </Badge>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span className="text-slate-400">Account</span>
                    <span className="max-w-[160px] truncate text-right font-mono text-slate-600 dark:text-slate-300">
                      {integration?.external_account_id ?? '—'}
                    </span>
                  </div>
                  {statusMessage(integration) ? (
                    <p className="rounded-md bg-amber-50 p-2 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                      {statusMessage(integration)}
                    </p>
                  ) : null}
                  <div>
                    <p className="mb-1.5 text-slate-400">Permissions</p>
                    <div className="flex flex-wrap gap-1">
                      {integration?.permissions.length ? (
                        integration.permissions.map((permission) => (
                          <Badge key={permission} tone="sky">{titleCase(permission)}</Badge>
                        ))
                      ) : (
                        <span className="text-slate-400">No permissions granted</span>
                      )}
                    </div>
                  </div>
                  {integration?.last_error ? (
                    <p className="rounded-md bg-rose-50 p-2 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300">
                      {integration.last_error}
                    </p>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-2 border-t border-slate-200 p-4 dark:border-slate-800">
                  {!integration ? (
                    <Button
                      variant="primary"
                      size="sm"
                      loading={busyKey === `connect:${provider.key}`}
                      onClick={() => void connect(provider.key)}
                    >
                      Connect
                    </Button>
                  ) : (
                    <>
                      {!connected ? (
                        <Button
                          variant="primary"
                          size="sm"
                          loading={busyKey === `connect:${provider.key}`}
                          onClick={() => void connect(provider.key)}
                        >
                          Reconnect
                        </Button>
                      ) : null}
                      <Button size="sm" loading={busyKey === `sync:${integration.id}`} onClick={() => void sync(integration)}>
                        Sync now
                      </Button>
                      <Button variant="danger" size="sm" loading={busyKey === `disconnect:${integration.id}`} onClick={() => void disconnect(integration)}>
                        Disconnect
                      </Button>
                    </>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {!loading && !integrations.length ? (
        <Card>
          <EmptyState title="No integrations connected" description="Connect a provider above to start syncing pipeline data." />
        </Card>
      ) : null}
    </div>
  );
}
