// OS notifications (Notification API) for finished background answers, with a plain fallback: the caller always
// shows an in-app toast; the OS notification is extra and only when the browser supports and allows it.

export const ASKED_KEY = "haki.notifications.asked";

export type NotifyResult = "shown" | "unsupported" | "denied" | "not-asked";

const api = (): typeof Notification | null =>
  typeof window !== "undefined" && "Notification" in window ? window.Notification : null;

function asked(storage: Storage | null): boolean {
  try {
    return storage?.getItem(ASKED_KEY) === "1";
  } catch {
    return false;
  }
}

function markAsked(storage: Storage | null): void {
  try {
    storage?.setItem(ASKED_KEY, "1");
  } catch {
    // Private windows may refuse storage; the worst case is being asked again next time.
  }
}

const browserStorage = (): Storage | null => {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

/** Ask for permission once per browser (only while undecided); later calls do nothing. */
export async function askPermissionOnce(storage: Storage | null = browserStorage()): Promise<void> {
  const notification = api();
  if (!notification || notification.permission !== "default" || asked(storage)) return;
  markAsked(storage);
  try {
    await notification.requestPermission();
  } catch {
    // Some engines throw instead of resolving "denied".
  }
}

/** Show an OS notification if allowed; clicking it focuses the window and runs onClick. */
export function notify(title: string, body: string, onClick: () => void): NotifyResult {
  const notification = api();
  if (!notification) return "unsupported";
  if (notification.permission === "denied") return "denied";
  if (notification.permission !== "granted") return "not-asked";
  try {
    const shown = new notification(title, { body, tag: "hakiai-answer" });
    shown.onclick = () => {
      window.focus();
      onClick();
      shown.close();
    };
    return "shown";
  } catch {
    // Chrome on Android only allows notifications from a service worker.
    return "unsupported";
  }
}
