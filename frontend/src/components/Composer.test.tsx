import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import limits from "../limits.json";
import { renderIn } from "../test/render";
import { Composer } from "./Composer";

function Harness({ busy = false, onSubmit }: { busy?: boolean; onSubmit: (q: string, l: string) => void }) {
  const [value, setValue] = useState("");
  return <Composer label="Your question" value={value} onChange={setValue} onSubmit={onSubmit} busy={busy} examples />;
}

function setup(busy = false) {
  const onSubmit = vi.fn();
  renderIn(<Harness busy={busy} onSubmit={onSubmit} />);
  return { onSubmit, box: screen.getByRole("textbox", { name: "Your question" }) };
}

test("the counter tracks the limit and input stops at it", () => {
  const { box } = setup();
  expect(box).toHaveAttribute("maxLength", String(limits.max_question_chars));
  fireEvent.change(box, { target: { value: "x".repeat(limits.max_question_chars) } });
  expect(
    screen.getByText(`${limits.max_question_chars} / ${limits.max_question_chars} characters`),
  ).toBeInTheDocument();
});

test("Ctrl+Enter submits the trimmed question in the chosen language; blank questions cannot be sent", async () => {
  const user = userEvent.setup();
  const { box, onSubmit } = setup();
  expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  await user.click(screen.getByRole("radio", { name: "Kiswahili" }));
  await user.type(box, "  Why was I fired?  ");
  await user.keyboard("{Control>}{Enter}{/Control}");
  expect(onSubmit).toHaveBeenCalledWith("Why was I fired?", "sw");
});

test("the answer language starts as the interface language", async () => {
  const onSubmit = vi.fn();
  renderIn(<Harness onSubmit={onSubmit} />, "sw");
  expect(screen.getByRole("radio", { name: "Kiswahili" })).toBeChecked();
});

test("example chips fill the box; the disclaimer is always shown", async () => {
  const user = userEvent.setup();
  const { box } = setup();
  await user.click(screen.getByRole("button", { name: /fired me without notice/ }));
  expect(box).toHaveValue("My employer fired me without notice. What are my rights?");
  expect(screen.getByText(/legal information, not legal advice/)).toBeInTheDocument();
});

test("nothing is submitted while an answer is in progress", async () => {
  const { box, onSubmit } = setup(true);
  fireEvent.change(box, { target: { value: "Another?" } });
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(onSubmit).not.toHaveBeenCalled();
});
