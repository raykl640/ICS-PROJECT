// Page-level keyboard shortcuts must not fire while the user types or a dialog is open.

/** True when a key press should go to a field or dialog, not to page shortcuts. */
export function isTyping(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return Boolean(
    element?.closest?.("input, textarea, select, [contenteditable=''], [contenteditable='true'], [role='dialog']"),
  );
}
