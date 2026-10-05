import { useEffect, useState } from "react";
import { ProgressSteps, type StepStatus } from "../design/components/ProgressSteps";
import type { Phase, SessionState } from "../hooks/session";
import { type StringKey, useI18n } from "../i18n";
import { etaSeconds, loadSpeed, splitDuration } from "../lib/eta";

// Which step is current in each busy phase; steps before it are done, after it waiting.
const CURRENT: Partial<Record<Phase, number>> = {
  searching: 0,
  retrieved: 1,
  queued: 1,
  generating: 2,
  translating: 3,
};

/** Date.now(), refreshed every second while active. */
function useNow(active: boolean): number {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

/** Searching → waiting in line (position) → writing (elapsed, ETA) → translating, for one answer. */
export function Progress({ state }: { state: SessionState }) {
  const { t } = useI18n();
  const current = CURRENT[state.phase] ?? 4;
  const now = useNow(current < 4);
  const [speed] = useState(loadSpeed);
  const time = (seconds: number) => {
    const { m, s } = splitDuration(seconds);
    return m ? t("time_min_sec", { m, s }) : t("time_sec", { s });
  };

  const writingDetail = () => {
    if (state.generatingAt === null) return undefined;
    const eta = etaSeconds(speed, state, now);
    const parts = [t("elapsed", { time: time((now - state.generatingAt) / 1000) })];
    if (eta !== null) parts.push(t("eta", { time: time(eta) }));
    return `${parts.join(", ")}. ${t("eta_note")}`;
  };

  const steps: { key: StringKey; detail?: string }[] = [
    {
      key: "step_search",
      detail: state.chunkCount === null ? undefined : t("status_retrieved", { count: state.chunkCount }),
    },
    {
      key: "step_queue",
      detail: state.queuePosition === null ? undefined : t("step_position", { position: state.queuePosition }),
    },
    { key: "step_write", detail: current === 2 ? writingDetail() : undefined },
    ...(state.language === "sw" ? [{ key: "step_translate" as const }] : []),
  ];
  const status = (index: number): StepStatus => (index < current ? "done" : index === current ? "current" : "todo");

  return (
    <ProgressSteps
      label={t("progress_label")}
      statusText={{ done: t("step_status_done"), current: t("step_status_current"), todo: t("step_status_todo") }}
      steps={steps.map((step, index) => ({ label: t(step.key), status: status(index), detail: step.detail }))}
    />
  );
}
