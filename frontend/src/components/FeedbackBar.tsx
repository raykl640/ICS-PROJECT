import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { postFeedback, type Rating } from "../api/client";
import { Button } from "../design/components/Button";
import { TextArea } from "../design/components/Field";
import { useI18n } from "../i18n";
import limits from "../limits.json";

type SendState = "open" | "sending" | "sent" | "failed";

const ICONS = { up: ThumbsUp, down: ThumbsDown } as const;

/** Thumbs up/down with an optional comment, sent once per session. */
export function FeedbackBar({ sessionId }: { sessionId: string }) {
  const { t } = useI18n();
  const [rating, setRating] = useState<Rating | null>(null);
  const [comment, setComment] = useState("");
  const [state, setState] = useState<SendState>("open");

  if (state === "sent") {
    return (
      <p role="status" className="text-sm font-semibold text-ink-muted">
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
    <section aria-labelledby="feedback-title">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="feedback-title" className="mr-1 text-sm text-ink-muted">
          {t("feedback_prompt")}
        </h2>
        {(["up", "down"] as const).map((value) => {
          const Icon = ICONS[value];
          return (
            <Button
              key={value}
              aria-pressed={rating === value}
              variant={rating === value ? "secondary" : "ghost"}
              icon={<Icon size={16} />}
              className="text-sm text-ink-muted aria-pressed:text-ink"
              onClick={() => setRating(value)}
            >
              {t(value === "up" ? "feedback_up" : "feedback_down")}
            </Button>
          );
        })}
      </div>
      {rating && (
        <div className="mt-3 flex max-w-xl flex-col items-start gap-3">
          <TextArea
            label={t("feedback_comment_label")}
            value={comment}
            maxLength={limits.max_comment_chars}
            rows={2}
            onChange={(event) => setComment(event.target.value)}
            frameClassName="w-full"
            className="min-h-16"
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" onClick={send} disabled={state === "sending"}>
              {t("feedback_send")}
            </Button>
            {state === "failed" && <span className="font-semibold text-danger">{t("error_generic")}</span>}
          </div>
          <p className="text-sm text-ink-muted">{t("feedback_privacy")}</p>
        </div>
      )}
    </section>
  );
}
