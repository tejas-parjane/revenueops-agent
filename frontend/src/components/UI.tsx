import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cx } from '../lib/cx';

type Tone = 'neutral' | 'sky' | 'emerald' | 'amber' | 'rose' | 'violet';

const badgeTones: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700',
  sky: 'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/30',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30',
  amber: 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30',
  violet: 'bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/30',
};

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cx('card-surface', className)}>{children}</section>;
}

export function CardHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
      <div className="min-w-0">
        <h2 className="section-title">{title}</h2>
        {description ? <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Badge({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset',
        badgeTones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status, label }: { status: string | null | undefined; label?: string }) {
  const value = (status ?? 'unknown').toLowerCase();
  let tone: Tone = 'neutral';

  if (['connected', 'active', 'completed', 'success', 'approved', 'synced', 'healthy'].includes(value)) tone = 'emerald';
  else if (['pending', 'running', 'in_progress', 'processing', 'needs_review', 'queued', 'awaiting_approval', 'review'].includes(value)) tone = 'amber';
  else if (['failed', 'error', 'rejected', 'disconnected', 'overdue', 'critical', 'expired'].includes(value)) tone = 'rose';
  else if (['high', 'urgent'].includes(value)) tone = 'rose';
  else if (['medium', 'warning', 'neglected'].includes(value)) tone = 'amber';
  else if (['investigating', 'analyzing', 'agent'].includes(value)) tone = 'violet';

  return (
    <Badge tone={tone}>
      <span className="mr-1 h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {label ?? (status || 'Unknown')}
    </Badge>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md';
  loading?: boolean;
};

export function Button({
  children,
  variant = 'secondary',
  size = 'md',
  loading = false,
  disabled,
  className,
  type = 'button',
  ...props
}: ButtonProps) {
  const variants = {
    primary: 'bg-sky-600 text-white hover:bg-sky-500 focus-visible:outline-sky-500 dark:bg-sky-500 dark:hover:bg-sky-400',
    secondary: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus-visible:outline-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800',
    danger: 'border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 focus-visible:outline-rose-500 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/20',
    ghost: 'text-slate-600 hover:bg-slate-100 focus-visible:outline-sky-500 dark:text-slate-300 dark:hover:bg-slate-800',
  };
  const sizes = {
    sm: 'px-2.5 py-1.5 text-xs',
    md: 'px-3.5 py-2 text-sm',
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium shadow-card transition-all duration-200 hover:shadow-card-lifted active:shadow-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {loading ? <Spinner className="h-3.5 w-3.5" /> : null}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cx('h-5 w-5 animate-spin text-current', className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-400 dark:bg-slate-800">
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
          <path d="M4 7h16M4 12h10M4 17h7" strokeLinecap="round" />
        </svg>
      </div>
      <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{title}</p>
      {description ? <p className="mt-1 max-w-sm text-xs text-slate-500 dark:text-slate-400">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

const metricTones = {
  sky: 'border-t-sky-500',
  emerald: 'border-t-emerald-500',
  amber: 'border-t-amber-500',
  rose: 'border-t-rose-500',
  violet: 'border-t-violet-500',
};

export function MetricCard({
  label,
  value,
  hint,
  tone = 'sky',
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: keyof typeof metricTones;
}) {
  return (
    <Card className={cx('border-t-2 p-4', metricTones[tone])}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900 dark:text-white">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hint}</p> : null}
    </Card>
  );
}

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx('overflow-x-auto', className)}>
      <table className="w-full border-collapse text-left">{children}</table>
    </div>
  );
}

export function TableHead({ children }: { children: ReactNode }) {
  return <thead className="hidden sm:table-header-group">{children}</thead>;
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TableRow({
  children,
  className,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <tr
      onClick={onClick}
      className={cx('transition hover:bg-slate-50 dark:hover:bg-slate-800/50', onClick ? 'cursor-pointer' : '', className)}
    >
      {children}
    </tr>
  );
}

export function TableHeader({ children, className }: { children?: ReactNode; className?: string }) {
  return <th className={cx('table-head', className)}>{children}</th>;
}

export function TableCell({
  children,
  className,
  title,
}: {
  children?: ReactNode;
  className?: string;
  title?: string;
}) {
  return <td className={cx('table-cell', className)} title={title}>{children}</td>;
}

export function JsonView({ value, className }: { value: unknown; className?: string }) {
  const text = value === undefined ? 'null' : JSON.stringify(value, null, 2);
  return (
    <pre
      className={cx(
        'max-h-64 overflow-auto rounded-md bg-slate-50 p-3 font-mono text-[11px] leading-relaxed text-slate-700 ring-1 ring-inset ring-slate-200 dark:bg-slate-950 dark:text-slate-300 dark:ring-slate-800',
        className,
      )}
    >
      {text}
    </pre>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
      <span>{message}</span>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="font-semibold underline underline-offset-2">
          Retry
        </button>
      ) : null}
    </div>
  );
}
