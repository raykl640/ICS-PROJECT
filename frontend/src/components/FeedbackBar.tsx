import { useState } from "react";
import { postFeedback, type Rating } from "../api/client";
import { useI18n } from "../i18n";
import limits from "../limits.json";
import { BUTTON_PRIMARY } from "./buttons";

type SendState = "open" | "sending" | "sent" | "failed";

const CHOICE =
  "inline-flex min-h-11 items-center gap-2 rounded-lg border px-4 py-2 font-semibold aria-pressed:border-brand aria-pressed:bg-brand aria-pressed:text-on-brand border-line bg-surface hover:border-brand";

/** Thumbs up/down with an optional comment, sent once per session. */
export function FeedbackBar({ sessionId }: { sessionId: string }) {
  const { t } = useI18n();
  const [rating, setRating] = useState<Rating | null>(null);
  const [comment, setComment] = useState("");
  const [state, setState] = useState<SendState>("open");

  if (state === "sent") {
    return (
      <p role="status" className="rounded-xl border border-line bg-surface px-5 py-4 font-medium">
        {t("feedback_thanks")}
      </p>
    );
  }

  const send = async () => {
    if (!rating) return;
    setState("sending");
    try {
      await postFeedback(sessionId, rating, comment.trim());
      setState("sent");
    } catch {
      setState("failed");
    }
  };

  return (
    <section aria-labelledby="feedback-title" className="rounded-xl border border-line bg-surface px-5 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="feedback-title" className="w-full font-semibold sm:w-auto">
          {t("feedback_prompt")}
        </h2>
        {(["up", "down"] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={rating === value}
            onClick={() => setRating(value)}
            className={CHOICE}
          >
            <span aria-hidden="true">{value === "up" ? "👍" : "👎"}</span>
            {t(value === "up" ? "feedback_up" : "feedback_down")}
          </button>
        ))}
      </div>
      {rating && (
        <div className="mt-4 space-y-3">
          <label htmlFor="feedback-comment" className="block text-base font-medium">
            {t("feedback_comment_label")}
          </label>
          <textarea
            id="feedback-comment"
            value={comment}
            maxLength={limits.max_comment_chars}
            rows={2}
            onChange={(event) => setComment(event.target.value)}
            className="block w-full rounded-lg border border-line bg-paper px-3 py-2 text-base focus:border-brand"
          />
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" onClick={send} disabled={state === "sending"} className={BUTTON_PRIMARY}>
              {t("feedback_send")}
            </button>
            {state === "failed" && <span className="text-danger-ink">{t("error_generic")}</span>}
          </div>
        </div>
      )}
      <p className="mt-3 text-sm text-muted">{t("feedback_privacy")}</p>
    </section>
  );
}
