import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { ApiError, repositoriesApi, type RepositoryResponse } from "../lib/api";

export function RepositoriesPage() {
  const [repositories, setRepositories] = useState<RepositoryResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [name, setName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  async function refresh() {
    setIsLoading(true);
    try {
      setRepositories(await repositoriesApi.list());
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsCreating(true);
    try {
      await repositoriesApi.create(name, sourceUrl);
      setName("");
      setSourceUrl("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create repository.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="mb-3 text-xl font-semibold">Ingest a repository</h1>
        <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            Name
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-48 rounded border border-slate-300 px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
            />
          </label>
          <label className="text-sm">
            Source URL (https)
            <input
              required
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://github.com/owner/repo.git"
              className="mt-1 block w-80 rounded border border-slate-300 px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
            />
          </label>
          <button
            type="submit"
            disabled={isCreating}
            className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
          >
            {isCreating ? "Submitting..." : "Ingest"}
          </button>
        </form>
        {error && (
          <p role="alert" className="mt-2 text-sm text-red-600">
            {error}
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Your repositories</h2>
        {isLoading ? (
          <p className="text-slate-500">Loading...</p>
        ) : repositories.length === 0 ? (
          <p className="text-slate-500">No repositories yet. Ingest one above.</p>
        ) : (
          <ul className="divide-y divide-slate-200 rounded border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
            {repositories.map((repo) => (
              <li key={repo.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <Link to={`/repositories/${repo.id}`} className="font-medium underline">
                    {repo.name}
                  </Link>
                  <p className="text-xs text-slate-500">{repo.source_url}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500">
                    {repo.file_count} files / {repo.chunk_count} chunks
                  </span>
                  <StatusBadge status={repo.status} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
