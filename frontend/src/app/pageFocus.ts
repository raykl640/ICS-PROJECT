// After a client-side navigation, the new page's <h1> takes focus so screen readers announce where the user is.
let pending = false;

/** Ask the next PageTitle to take focus (called by the shell on navigation). */
export function requestPageFocus(): void {
  pending = true;
}

/** True once after requestPageFocus. */
export function takePageFocus(): boolean {
  const wanted = pending;
  pending = false;
  return wanted;
}
