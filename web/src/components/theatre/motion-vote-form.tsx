"use client";

import { useEffect, useState } from "react";

import { SpeakerAvatar } from "@/components/avatar";
import { useT } from "@/components/settings-provider";
import { speakerMeta } from "@/lib/countries";

export type HumanMotionVote = "pour" | "contre" | "abstention";

const CHOICES: { vote: HumanMotionVote; key: string; active: string }[] = [
  { vote: "pour", key: "motion.vote.pour", active: "border-good bg-good/10 text-good" },
  { vote: "contre", key: "motion.vote.contre", active: "border-bad bg-bad/10 text-bad" },
  {
    vote: "abstention",
    key: "motion.vote.abstention",
    active: "border-warn bg-warn/10 text-warn",
  },
];

export function MotionVoteForm({
  country,
  target,
  deadlineTs,
  onSubmit,
}: {
  country: string;
  target: string;
  deadlineTs?: number;
  onSubmit: (vote: HumanMotionVote) => Promise<void>;
}) {
  const t = useT();
  const [choice, setChoice] = useState<HumanMotionVote | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now() / 1000);

  useEffect(() => {
    if (!deadlineTs) return;
    const timer = setInterval(() => setNow(Date.now() / 1000), 250);
    return () => clearInterval(timer);
  }, [deadlineTs]);

  const remaining = deadlineTs ? Math.max(0, deadlineTs - now) : null;
  const urgent = remaining !== null && remaining <= 10;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!choice || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(choice);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className={`rounded-lg border bg-surface p-4 ${urgent ? "border-bad" : "border-warn/60"}`}
      aria-label={t("motion.vote.aria")}
    >
      <div className="flex flex-wrap items-center gap-2">
        <SpeakerAvatar id={country} size={22} />
        <span className="font-semibold">{speakerMeta(country).label}</span>
        <span className={`text-sm font-medium ${urgent ? "text-bad" : "text-warn"}`}>
          {t("motion.vote.a-toi")}
        </span>
        {remaining !== null && (
          <span
            className={`rounded-md border px-2 py-0.5 font-mono text-xs tabular-nums ${
              urgent ? "border-bad text-bad" : "border-warn/50 text-warn"
            }`}
            aria-live={urgent ? "assertive" : "off"}
          >
            {Math.ceil(remaining)} s
          </span>
        )}
      </div>
      <p className="mt-2 text-sm text-fg-muted">
        {t("motion.vote.question").replace("{pays}", speakerMeta(target).label)}
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {CHOICES.map(({ vote, key, active }) => (
          <button
            key={vote}
            type="button"
            aria-pressed={choice === vote}
            onClick={() => setChoice(vote)}
            disabled={submitting}
            className={`cursor-pointer rounded-md border px-3 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              choice === vote
                ? active
                : "border-edge bg-surface-2 text-fg-muted hover:border-edge-strong"
            }`}
          >
            {t(key)}
          </button>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs text-fg-faint">{t("motion.vote.silence")}</span>
        <button
          type="submit"
          disabled={!choice || submitting}
          className="cursor-pointer rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? t("motion.vote.validation") : t("motion.vote.valider")}
        </button>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-xs text-bad">
          {t("motion.vote.erreur")} {error}
        </p>
      )}
    </form>
  );
}
