import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { errorMessage } from '../lib/api';
import { Button, ErrorBanner } from '../components/UI';

export default function Register() {
  const { register, user, loading } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [organizationName, setOrganizationName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await register({ full_name: fullName, organization_name: organizationName, email, password });
      navigate('/', { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <div className="brand-mark text-sm">R</div>
          <div>
            <p className="font-semibold text-slate-900 dark:text-white">RevenueOps Agent</p>
            <p className="text-[11px] uppercase tracking-widest text-brand-deep">Operations command center</p>
          </div>
        </div>

        <div className="card-surface p-6">
          <h1 className="page-title text-slate-900 dark:text-white">Create your workspace</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Set up your organization and administrator account.</p>

          {error ? <div className="mt-5"><ErrorBanner message={error} /></div> : null}

          <form onSubmit={(event) => void handleSubmit(event)} className="mt-5 space-y-4">
            <div>
              <label className="label-field" htmlFor="full_name">Full name</label>
              <input id="full_name" required value={fullName} onChange={(event) => setFullName(event.target.value)} className="input-field" placeholder="Alex Morgan" />
            </div>
            <div>
              <label className="label-field" htmlFor="organization_name">Organization</label>
              <input id="organization_name" required value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} className="input-field" placeholder="Acme Revenue" />
            </div>
            <div>
              <label className="label-field" htmlFor="email">Work email</label>
              <input id="email" type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="input-field" placeholder="you@company.com" />
            </div>
            <div>
              <label className="label-field" htmlFor="password">Password</label>
              <input id="password" type="password" required minLength={8} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className="input-field" placeholder="At least 8 characters" />
            </div>
            <Button type="submit" variant="primary" loading={submitting} className="w-full">
              Create organization
            </Button>
          </form>
        </div>

        <p className="mt-5 text-center text-sm text-slate-500 dark:text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-brand-deep hover:underline dark:text-brand">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
