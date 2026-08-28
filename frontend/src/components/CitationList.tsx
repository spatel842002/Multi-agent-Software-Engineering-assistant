import type { CitationResponse } from "../lib/api";

export function CitationList({ citations }: { citations: CitationResponse[] }) {
  if (citations.length === 0) {
    return <p className="text-sm text-slate-500">No citations were resolved for this answer.</p>;
  }

  return (
    <ul className="space-y-1" aria-label="Citations">
      {citations.map((c, i) => (
        <li
          key={`${c.file_path}:${c.start_line}:${i}`}
          className="font-mono text-xs text-slate-600 dark:text-slate-400"
        >
          {c.file_path}:{c.start_line}-{c.end_line}
        </li>
      ))}
    </ul>
  );
}
