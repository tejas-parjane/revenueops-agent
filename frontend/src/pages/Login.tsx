import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { errorMessage } from '../lib/api';
import { Button, ErrorBanner } from '../components/UI';

export default function Login() {
  const { login, user, loading } = useAuth();
  const navigate = useNavigate();
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
      await login(email, password);
      navigate('/', { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell flex min-h-screen">
      <div className="auth-hero relative hidden w-1/2 flex-col justify-between overflow-hidden p-12 lg:flex">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-brand/20 blur-3xl" />
        <div className="absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-butter/20 blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="brand-mark text-sm">R</div>
            <span className="text-lg font-semibold">RevenueOps Agent</span>
          </div>
        </div>
        <div className="relative max-w-md">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-sky-300">Operations command center</p>
          <h1 className="text-4xl font-semibold leading-tight">Turn pipeline risk into controlled action.</h1>
          <p className="mt-4 text-sm leading-6 text-cream/80">
            Monitor revenue signals, investigate with an AI agent, and approve every outbound action before it executes.
          </p>
        </div>
        <div className="relative grid grid-cols-3 gap-3 text-xs text-cream/80">
          <div className="auth-chip p-3">Multi-tenant by design</div>
          <div className="auth-chip p-3">Human-in-the-loop</div>
          <div className="auth-chip p-3">Audit-ready actions</div>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="brand-mark text-sm">R</div>
          </div>
          <h2 className="page-title text-slate-900 dark:text-white">Sign in</h2>
          <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">Access your organization workspace.</p>

          <div className="mt-7 card-surface p-5">
            {error ? <ErrorBanner message={error} /> : null}
            <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
              <div>
                <label className="label-field" htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@company.com"
                  className="input-field"
                />
              </div>
              <div>
                <label className="label-field" htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="••••••••"
                  className="input-field"
                />
              </div>
              <Button type="submit" variant="primary" loading={submitting} className="w-full">
                Sign in
              </Button>
            </form>
          </div>

          <p className="mt-5 text-center text-sm text-slate-500 dark:text-slate-400">
            New here?{' '}
            <Link to="/register" className="font-semibold text-brand-deep hover:underline dark:text-brand">
              Create an organization
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
