import { useEffect, useRef, useState } from "react";

export const ANNOUNCE_INTERVAL_MS = 4000;

/** Index just past the last sentence end (". ", "\n", ...) in text, or 0. */
function sentenceCut(text: string): number {
  let cut = 0;
  for (const match of text.matchAll(/[.!?:;]\s|\n/g)) cut = match.index + match[0].length;
  return cut;
}

/** Throttled screen-reader text for a growing answer: complete sentences every interval, the rest once finished.
 * Text that is not a continuation (a replay or the translation) starts over. */
export function useAnnouncement(text: string, finished: boolean, intervalMs = ANNOUNCE_INTERVAL_MS): string {
  const [announcement, setAnnouncement] = useState("");
  const latest = useRef(text);
  const spoken = useRef("");

  useEffect(() => {
    latest.current = text;
    if (!text.startsWith(spoken.current)) spoken.current = "";
  }, [text]);

  useEffect(() => {
    const speak = (all: boolean) => {
      const fresh = latest.current.slice(spoken.current.length);
      const cut = all ? fresh.length : sentenceCut(fresh);
      if (!fresh.slice(0, cut).trim()) return;
      spoken.current += fresh.slice(0, cut);
      setAnnouncement(fresh.slice(0, cut).trim());
    };
    if (finished) {
      const flush = setTimeout(() => speak(true), 0);
      return () => clearTimeout(flush);
    }
    const id = setInterval(() => speak(false), intervalMs);
    return () => clearInterval(id);
  }, [finished, intervalMs]);

  return announcement;
}
