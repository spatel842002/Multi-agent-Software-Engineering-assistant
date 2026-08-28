import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { ApiError, patchesApi, type PatchProposalResponse } from "../lib/api";

export function PatchProposalPage() {
  const { id } = useParams<{ id: string }>();
  const [proposal, setProposal] = useState<PatchProposalResponse | null>(null);
  const [reason, setReason] = useState("");
  const [isDeciding, setIsDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!id) return;
    setProposal(await patchesApi.get(id));
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function decide(decision: "approve" | "reject") {
    if (!id) return;
    setError(null);
    setIsDeciding(true);
    try {
      const updated = await patchesApi.decide(id, decision, reason || undefined);
      setProposal(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record decision.");
    } finally {
      setIsDeciding(false);
    }
  }

  if (!proposal) return <p className="text-slate-500">Loading...</p>;

  const isPending = proposal.status === "pending_approval";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Patch proposal</h1>
        <div className="mt-1 flex items-center gap-2">
          <StatusBadge status={proposal.status} />
          <span className="text-xs text-slate-500">{proposal.target_files.join(", ")}</span>
        </div>
      </div>

      <p className="rounded border border-sky-300 bg-sky-50 px-3 py-2 text-sm text-sky-800 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-200">
        Nothing in this proposal has been applied or executed. Approving it applies the diff and runs the test
        command only inside a disposable sandbox copy of the repository.
      </p>

      <div>
        <h2 className="mb-1 text-sm font-medium">Diff</h2>
        <pre className="max-h-96 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
          <code>{proposal.diff_text}</code>
        </pre>
      </div>

      {proposal.test_command && (
        <div>
          <h2 className="mb-1 text-sm font-medium">Test command</h2>
          <code className="text-xs">{proposal.test_command}</code>
        </div>
      )}

      {proposal.test_output && (
        <div>
          <h2 className="mb-1 text-sm font-medium">Sandbox output</h2>
          <pre className="max-h-64 overflow-auto rounded bg-slate-100 p-3 text-xs dark:bg-slate-900">
            {proposal.test_output}
          </pre>
        </div>
      )}

      {isPending && (
        <div className="space-y-2 rounded border border-slate-200 p-4 dark:border-slate-800">
          <label className="block text-sm">
            Reason (optional)
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
            />
          </label>
          <div className="flex gap-2">
            <button
              onClick={() => decide("approve")}
              disabled={isDeciding}
              className="rounded bg-emerald-600 px-3 py-2 text-sm text-white disabled:opacity-50"
            >
              Approve &amp; run in sandbox
            </button>
            <button
              onClick={() => decide("reject")}
              disabled={isDeciding}
              className="rounded bg-red-600 px-3 py-2 text-sm text-white disabled:opacity-50"
            >
              Reject
            </button>
          </div>
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
