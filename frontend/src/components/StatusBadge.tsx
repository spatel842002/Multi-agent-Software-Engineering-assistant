const COLORS: Record<string, string> = {
  pending: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  cloning: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  indexing: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  ready: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  pending_approval: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  approved: "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-200",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  test_run_passed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
  test_run_failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  applied: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
};

export function StatusBadge({ status }: { status: string }) {
  const classes = COLORS[status] ?? "bg-slate-200 text-slate-700";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${classes}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
