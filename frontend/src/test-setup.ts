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
  vi.mocked(console.error).mockRestore();
  expect(errors.map((args) => args.map(String).join(" "))).toEqual([]);
});
