import { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { clearToken } from '../lib/api';
import { useAuth } from '../lib/auth';
import { cx } from '../lib/cx';
import { useTheme } from '../lib/theme';

const navigation = [
  { path: '/', label: 'Overview', icon: 'overview' },
  { path: '/pipeline', label: 'Pipeline', icon: 'pipeline' },
  { path: '/agent', label: 'AI Agent', icon: 'agent' },
  { path: '/approvals', label: 'Approvals', icon: 'approvals' },
  { path: '/activity', label: 'Activity', icon: 'activity' },
  { path: '/integrations', label: 'Integrations', icon: 'integrations' },
  { path: '/settings', label: 'Settings', icon: 'settings' },
] as const;

const iconPaths: Record<string, string> = {
  overview: 'M4 13h6V4H4v9zm0 7h6v-5H4v5zm10 0h6v-9h-6v9zm0-16v5h6V4h-6z',
  pipeline: 'M4 5h16M4 12h10M4 19h6M17 10l3 2-3 2',
  agent: 'M12 3l1.9 4.6L18.5 9.5 13.9 11.4 12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3zm6 11l.9 2.1L21 17l-2.1.9L18 20l-.9-2.1L15 17l2.1-.9L18 14z',
  approvals: 'M9 12l2 2 4-4M12 3l7 4v5c0 4.4-3 8.4-7 9-4-.6-7-4.6-7-9V7l7-4z',
  activity: 'M3 12h4l3-7 4 14 3-7h4',
  integrations: 'M10 13a5 5 0 007.5.5l2-2a5 5 0 00-7-7l-1 1M14 11a5 5 0 00-7.5-.5l-2 2a5 5 0 007 7l1-1',
  settings: 'M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7zm8-3.5l-2-.4-.6-1.5 1.1-1.7-1.8-1.8-1.7 1.1-1.5-.6L13 4h-2l-.4 2-.6 1.5-1.7-1.1-1.8 1.8L7.6 10l-.6 1.5L5 12l2 .4.6 1.5-1.1 1.7 1.8 1.8 1.7-1.1 1.5.6.4 2h2l.4-2 1.5-.6 1.7 1.1 1.8-1.8-1.1-1.7.6-1.5L20 12z',
};

function NavIcon({ name }: { name: string }) {
  return (
    <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={iconPaths[name]} />
    </svg>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { organization, user } = useAuth();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center gap-2.5 border-b border-slate-200 px-4 dark:border-slate-800">
        <div className="brand-mark h-7 w-7 rounded-lg text-xs">R</div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">RevenueOps</p>
          <p className="truncate text-[10px] uppercase tracking-widest text-slate-400">Agent Console</p>
        </div>
      </div>

      <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Workspace</p>
        <p className="mt-1 truncate text-sm font-medium text-slate-700 dark:text-slate-200">{organization?.name ?? 'Organization'}</p>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
        {navigation.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cx(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition',
                isActive
                  ? 'bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100',
              )
            }
          >
            <NavIcon name={item.icon} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-slate-200 px-4 py-3 dark:border-slate-800">
        <p className="truncate text-xs font-medium text-slate-700 dark:text-slate-200">{user?.full_name ?? 'User'}</p>
        <p className="truncate text-[11px] text-slate-400">{user?.email ?? ''}</p>
      </div>
    </div>
  );
}

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const { user, organization, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  const currentPage = navigation.find((item) => item.path === location.pathname)?.label ?? 'Overview';

  async function handleLogout() {
    setSigningOut(true);
    try {
      await logout();
    } catch {
      clearToken();
    } finally {
      setMenuOpen(false);
      setMobileOpen(false);
      navigate('/login', { replace: true });
      setSigningOut(false);
    }
  }

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r border-slate-200 bg-white/85 backdrop-blur-xl lg:block dark:border-slate-800 dark:bg-slate-900/85">
        <SidebarContent />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-slate-950/50"
          />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-slate-200 bg-white/95 shadow-card backdrop-blur-xl dark:border-slate-800 dark:bg-slate-900/95">
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-slate-200 bg-white/80 px-4 backdrop-blur-xl lg:px-6 dark:border-slate-800 dark:bg-slate-900/80">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden dark:hover:bg-slate-800"
              aria-label="Open navigation"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
              </svg>
            </button>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{currentPage}</p>
              <p className="hidden truncate text-[11px] text-slate-400 sm:block">{organization?.name ?? 'Organization'}</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="rounded-md p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Light theme' : 'Dark theme'}
            >
              {theme === 'dark' ? (
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4l1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
                </svg>
              ) : (
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 105 10.5z" />
                </svg>
              )}
            </button>

            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                className="flex items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-[10px] font-semibold text-white dark:bg-slate-200 dark:text-slate-900">
                  {(user?.full_name ?? 'U').slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden max-w-28 truncate sm:inline">{user?.full_name ?? 'Account'}</span>
                <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 9l6 6 6-6" strokeLinecap="round" />
                </svg>
              </button>

              {menuOpen ? (
                <div className="absolute right-0 top-full z-40 mt-2 w-56 rounded-md border border-slate-200 bg-white p-1.5 shadow-lg dark:border-slate-700 dark:bg-slate-900">
                  <div className="border-b border-slate-100 px-2 py-2 dark:border-slate-800">
                    <p className="truncate text-xs font-semibold text-slate-800 dark:text-slate-200">{user?.full_name}</p>
                    <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      navigate('/settings');
                    }}
                    className="mt-1 w-full rounded px-2 py-1.5 text-left text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    Settings
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleLogout()}
                    disabled={signingOut}
                    className="w-full rounded px-2 py-1.5 text-left text-sm text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:text-rose-400 dark:hover:bg-rose-500/10"
                  >
                    {signingOut ? 'Signing out…' : 'Log out'}
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[1600px] p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
