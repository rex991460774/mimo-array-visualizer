import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Job } from "../api/types";

const POLL_MS = 500;

/** Start a server export job, poll it, and download the result when it is ready. */
export function useExportJob() {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  const stopPolling = () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
  };

  useEffect(() => stopPolling, []);

  const poll = useCallback((id: string, autoDownload: boolean) => {
    const step = async () => {
      try {
        const next = await api.job(id);
        setJob(next);
        if (next.status === "succeeded") {
          if (autoDownload) download(next);
          return;
        }
        if (next.status === "failed" || next.status === "cancelled") return;
      } catch (reason) {
        setError(errorMessage(reason));
        return;
      }
      timer.current = window.setTimeout(step, POLL_MS);
    };
    step();
  }, []);

  const start = useCallback(
    async (create: () => Promise<Job>, autoDownload = true) => {
      stopPolling();
      setError(null);
      try {
        const created = await create();
        setJob(created);
        poll(created.id, autoDownload);
      } catch (reason) {
        setJob(null);
        setError(errorMessage(reason));
      }
    },
    [poll],
  );

  const cancel = useCallback(async () => {
    if (!job) return;
    try {
      setJob(await api.cancelJob(job.id));
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }, [job]);

  const reset = useCallback(() => {
    stopPolling();
    setJob(null);
    setError(null);
  }, []);

  const running = job?.status === "queued" || job?.status === "running";
  return { job, error, running, start, cancel, reset, download: () => job && download(job) };
}

function download(job: Job) {
  const anchor = document.createElement("a");
  anchor.href = api.jobDownloadUrl(job.id);
  anchor.download = job.download_name ?? "";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}
