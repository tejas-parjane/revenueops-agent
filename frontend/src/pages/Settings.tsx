import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, errorMessage } from '../lib/api';
import { useAuth } from '../lib/auth';
import { formatDate } from '../lib/format';
import { useTheme } from '../lib/theme';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/UI';
import type { Invitation, Member, Organization } from '../types';

export default function Settings() {
  const { user, organization: authOrganization } = useAuth();
  const { theme, setTheme } = useTheme();
  const [organization, setOrganization] = useState<Organization | null>(authOrganization);
  const [members, setMembers] = useState<Member[]>([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('member');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [org, people] = await Promise.all([
        api.get<Organization>('/organizations/current'),
        api.get<Member[]>('/organizations/members'),
      ]);
      setOrganization(org);
      setMembers(people);
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

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      const invitation = await api.post<Invitation>('/organizations/invitations', { email, role });
      setSuccess(`Invitation created for ${invitation.email}.`);
      setEmail('');
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title text-slate-900 dark:text-white">Settings</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Manage your workspace, people, and interface preferences.</p>
      </div>

      {error ? <ErrorBanner message={error} onRetry={() => void load()} /> : null}

      <div className="grid gap-5 xl:grid-cols-3">
        <div className="space-y-5 xl:col-span-2">
          <Card>
            <CardHeader title="Organization" description="Current tenant details" />
            {loading && !organization ? (
              <div className="flex h-32 items-center justify-center text-slate-400"><Spinner /></div>
            ) : (
              <dl className="grid gap-4 p-4 sm:grid-cols-2">
                <div>
                  <dt className="label-field">Name</dt>
                  <dd className="text-sm font-medium text-slate-800 dark:text-slate-200">{organization?.name ?? '—'}</dd>
                </div>
                <div>
                  <dt className="label-field">Created</dt>
                  <dd className="text-sm font-medium text-slate-800 dark:text-slate-200">{formatDate(organization?.created_at)}</dd>
                </div>
                <div>
                  <dt className="label-field">Organization ID</dt>
                  <dd className="font-mono text-xs text-slate-600 dark:text-slate-300">{organization?.id ?? '—'}</dd>
                </div>
                <div>
                  <dt className="label-field">Signed in as</dt>
                  <dd className="text-sm text-slate-800 dark:text-slate-200">{user?.full_name ?? '—'} <span className="text-slate-400">({user?.email})</span></dd>
                </div>
              </dl>
            )}
          </Card>

          <Card>
            <CardHeader title="Members" description={`${members.length} people in this workspace`} />
            {members.length ? (
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeader>Name</TableHeader>
                    <TableHeader>Email</TableHeader>
                    <TableHeader>Role</TableHeader>
                    <TableHeader>Added</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {members.map((member) => (
                    <TableRow key={member.id}>
                      <TableCell className="font-medium text-slate-900 dark:text-slate-100">{member.full_name}</TableCell>
                      <TableCell>{member.email}</TableCell>
                      <TableCell><Badge tone={member.role === 'admin' ? 'violet' : 'neutral'}>{member.role}</Badge></TableCell>
                      <TableCell className="whitespace-nowrap">{formatDate(member.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState title="No members found" />
            )}
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader title="Invite a member" description="Send a workspace invitation" />
            <form onSubmit={(event) => void invite(event)} className="space-y-3 p-4">
              {success ? (
                <p className="rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">{success}</p>
              ) : null}
              <div>
                <label className="label-field" htmlFor="invite-email">Email</label>
                <input
                  id="invite-email"
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="teammate@company.com"
                  className="input-field"
                />
              </div>
              <div>
                <label className="label-field" htmlFor="invite-role">Role</label>
                <select id="invite-role" value={role} onChange={(event) => setRole(event.target.value)} className="input-field">
                  <option value="admin">Admin</option>
                  <option value="member">Member</option>
                  <option value="viewer">Viewer</option>
                </select>
              </div>
              <Button type="submit" variant="primary" loading={submitting} className="w-full">
                Send invitation
              </Button>
            </form>
          </Card>

          <Card>
            <CardHeader title="Appearance" description="Choose your interface theme" />
            <div className="p-4">
              <div className="grid grid-cols-2 gap-2 rounded-md bg-slate-100 p-1 dark:bg-slate-950">
                <button
                  type="button"
                  onClick={() => setTheme('light')}
                  className={`rounded px-3 py-2 text-sm font-medium transition ${theme === 'light' ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white' : 'text-slate-500'}`}
                >
                  Light
                </button>
                <button
                  type="button"
                  onClick={() => setTheme('dark')}
                  className={`rounded px-3 py-2 text-sm font-medium transition ${theme === 'dark' ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white' : 'text-slate-500'}`}
                >
                  Dark
                </button>
              </div>
              <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">Theme preference is stored locally in this browser.</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
