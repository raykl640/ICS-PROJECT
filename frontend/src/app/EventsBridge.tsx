// Signed in and unlocked: listen to /api/events and turn finished background answers into a toast (always),
// an OS notification (when allowed) and a library refresh.
import { useEffect } from "react";
import { useNavigate } from "react-router";
import { EVENTS_URL } from "../api/client";
import { useToast } from "../design/components/toastContext";
import { useI18n } from "../i18n";
import { notify } from "../lib/notify";
import { useAuth, useLibrary } from "./contexts";

interface TurnEvent {
  session_id: string;
  conversation_id: string | null;
}

export function EventsBridge() {
  const { me } = useAuth();
  const { bump } = useLibrary();
  const toast = useToast();
  const navigate = useNavigate();
  const { t } = useI18n();
  const unlocked = Boolean(me?.user && !me.locked);

  useEffect(() => {
    if (!unlocked || typeof EventSource === "undefined") return;
    const source = new EventSource(EVENTS_URL);
    const handle = (done: boolean) => (event: Event) => {
      const data = JSON.parse((event as MessageEvent<string>).data) as TurnEvent;
      bump();
      const href = data.conversation_id ? `/ask/${data.conversation_id}` : "/ask";
      const here = window.location.pathname === href && document.visibilityState === "visible";
      if (here) return;
      const title = t(done ? "answer_ready" : "answer_failed");
      const body = t(done ? "answer_ready_body" : "answer_failed_body");
      const open = () => navigate(href);
      toast({
        title,
        description: body,
        tone: done ? "success" : "danger",
        action: { label: t("answer_ready_open"), onSelect: open },
      });
      if (document.visibilityState !== "visible" || window.location.pathname !== href) notify(title, body, open);
    };
    source.addEventListener("turn_done", handle(true));
    source.addEventListener("turn_failed", handle(false));
    return () => source.close();
  }, [unlocked, bump, navigate, t, toast]);

  return null;
}
