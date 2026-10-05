import "@testing-library/jest-dom/vitest";

// React reports bugs (duplicate keys, act() misuse, bad props) through console.error: fail the test on any of them.
let errors: unknown[][] = [];

beforeEach(() => {
  errors = [];
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    errors.push(args);
  });
});

afterEach(() => {
  // Settings and speed samples live in localStorage and on <html>: start every test clean.
  localStorage.clear();
  for (const name of ["theme", "contrast", "text", "motion"]) delete document.documentElement.dataset[name];
  vi.mocked(console.error).mockRestore();
  expect(errors.map((args) => args.map(String).join(" "))).toEqual([]);
});

// jsdom gaps that Radix primitives (popper sizing, pointer capture, scrolling) rely on.
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => {};
Element.prototype.scrollIntoView ??= () => {};
