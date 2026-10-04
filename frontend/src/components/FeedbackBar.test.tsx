import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { stubFetch } from "../test/http";
import { renderIn } from "../test/render";
import { FeedbackBar } from "./FeedbackBar";

afterEach(() => vi.unstubAllGlobals());

test("feedback is sent once with the optional comment, then replaced by thanks", async () => {
  const user = userEvent.setup();
  const calls = stubFetch({ "POST /api/feedback": { body: { recorded: true } } });
  renderIn(<FeedbackBar sessionId="s1" />);
  expect(screen.queryByRole("button", { name: "Send feedback" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /No/ }));
  await user.type(screen.getByRole("textbox", { name: /Anything to add/ }), "  Unclear steps ");
  await user.click(screen.getByRole("button", { name: "Send feedback" }));
  expect(await screen.findByText(/Thank you/)).toBeInTheDocument();
  expect(calls).toEqual([
    { method: "POST", url: "/api/feedback", body: { session_id: "s1", rating: "down", comment: "Unclear steps" } },
  ]);
  expect(screen.queryAllByRole("button")).toHaveLength(0);
});

test("a failed send can be retried", async () => {
  const user = userEvent.setup();
  let fail = true;
  const calls = stubFetch({
    "POST /api/feedback": () => (fail ? { status: 500, body: {} } : { body: { recorded: true } }),
  });
  renderIn(<FeedbackBar sessionId="s1" />);
  await user.click(screen.getByRole("button", { name: /Yes/ }));
  await user.click(screen.getByRole("button", { name: "Send feedback" }));
  expect(await screen.findByText("The answer could not be generated.")).toBeInTheDocument();
  fail = false;
  await user.click(screen.getByRole("button", { name: "Send feedback" }));
  expect(await screen.findByText(/Thank you/)).toBeInTheDocument();
  expect(calls).toHaveLength(2);
});
