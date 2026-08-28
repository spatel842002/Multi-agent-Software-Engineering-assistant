import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { CitationList } from "../components/CitationList";
import { StatusBadge } from "../components/StatusBadge";
import {
  ApiError,
  chatApi,
  repositoriesApi,
  type RepositoryResponse,
  type WorkflowResponse,
} from "../lib/api";

type WorkflowTab = "qa" | "bug" | "patch";

const TABS: { id: WorkflowTab; label: string; placeholder: string }[] = [
  { id: "qa", label: "Ask a question", placeholder: "How does authentication work in this repo?" },
  {
    id: "bug",
    label: "Investigate a bug",
    placeholder: "Describe the bug, error message, or stack trace...",
  },
  { id: "patch", label: "Propose a patch", placeholder: "Describe the change you want made..." },
];

export function RepositoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [repository, setRepository] = useState<RepositoryResponse | null>(null);
  const [tab, setTab] = useState<WorkflowTab>("qa");
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WorkflowResponse | null>(null);

  useEffect(() => {
    if (!id) return;
    repositoriesApi
      .get(id)
      .then(setRepository)
      .catch(() => setRepository(null));
    const interval = setInterval(() => {
      repositoriesApi
        .get(id)
        .then(setRepository)
        .catch(() => undefined);
    }, 3000);
    return () => clearInterval(interval);
  }, [id]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    setError(null);
    setIsSubmitting(true);
    setResult(null);
    try {
      const response =
        tab === "qa"
          ? await chatApi.askQuestion(id, input)
          : tab === "bug"
            ? await chatApi.investigateBug(id, input)
            : await chatApi.proposePatch(id, input);
      setResult(response);
      setInput("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!repository) return <p className="text-slate-500">Loading...</p>;

  const isReady = repository.status === "ready";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{repository.name}</h1>
        <p className="text-xs text-slate-500">{repository.source_url}</p>
        <div className="mt-2 flex items-center gap-3 text-sm">
          <StatusBadge status={repository.status} />
          <span className="text-slate-500">
            {repository.file_count} files &middot; {repository.symbol_count} symbols &middot;{" "}
            {repository.chunk_count} chunks
          </span>
        </div>
        {repository.status_detail && <p className="mt-1 text-sm text-red-600">{repository.status_detail}</p>}
      </div>

      {!isReady && (
        <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          Ingestion is still in progress. Workflows become available once the repository status is "ready".
        </p>
      )}

      <div className="flex gap-2 border-b border-slate-200 dark:border-slate-800">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => {
              setTab(t.id);
              setResult(null);
              setError(null);
            }}
            className={`px-3 py-2 text-sm ${
              tab === t.id
                ? "border-b-2 border-slate-900 font-medium dark:border-slate-100"
                : "text-slate-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          required
          disabled={!isReady}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={TABS.find((t) => t.id === tab)?.placeholder}
          rows={4}
          className="w-full rounded border border-slate-300 px-3 py-2 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900"
        />
        <button
          type="submit"
          disabled={!isReady || isSubmitting}
          className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {isSubmitting ? "Working..." : "Submit"}
        </button>
      </form>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      {result && (
        <div className="space-y-3 rounded border border-slate-200 p-4 dark:border-slate-800">
          <p className="whitespace-pre-wrap text-sm">{result.answer}</p>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>prompt {result.prompt_version}</span>
            <span>{result.latency_ms}ms</span>
          </div>
          <CitationList citations={result.citations} />
          {result.patch_proposal_id && (
            <Link
              to={`/patch-proposals/${result.patch_proposal_id}`}
              className="inline-block text-sm underline"
            >
              Review this patch proposal &rarr;
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
