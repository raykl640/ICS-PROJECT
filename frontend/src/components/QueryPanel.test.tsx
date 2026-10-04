import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import limits from "../limits.json";
import { renderIn } from "../test/render";
import { QueryPanel } from "./QueryPanel";

function setup(busy = false) {
  const onSubmit = vi.fn();
  const onLanguage = vi.fn();
  renderIn(
    <QueryPanel busy={busy} compact={false} onLanguage={onLanguage} onSubmit={onSubmit} textareaRef={createRef()} />,
  );
  return { onSubmit, onLanguage, box: screen.getByRole("textbox", { name: "Your question" }) };
}

test("the counter tracks the limit and input stops at it", () => {
  const { box } = setup();
  expect(box).toHaveAttribute("maxLength", String(limits.max_question_chars));
  fireEvent.change(box, { target: { value: "x".repeat(limits.max_question_chars) } });
  expect(
    screen.getByText(`${limits.max_question_chars} / ${limits.max_question_chars} characters`),
  ).toBeInTheDocument();
});

test("Ctrl+Enter submits the trimmed question; blank questions cannot be sent", async () => {
  const user = userEvent.setup();
  const { box, onSubmit } = setup();
  expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  await user.type(box, "  Why was I fired?  ");
  await user.keyboard("{Control>}{Enter}{/Control}");
  expect(onSubmit).toHaveBeenCalledWith("Why was I fired?");
});

test("example chips fill the box and the language choice is reported", async () => {
  const user = userEvent.setup();
  const { box, onLanguage } = setup();
  await user.click(screen.getByRole("button", { name: /fired me without notice/ }));
  expect(box).toHaveValue("My employer fired me without notice. What are my rights?");
  await user.click(screen.getByRole("radio", { name: "Kiswahili" }));
  expect(onLanguage).toHaveBeenCalledWith("sw");
  expect(screen.getByText(/legal information, not legal advice/)).toBeInTheDocument();
});

test("nothing is submitted while an answer is in progress", async () => {
  const { box, onSubmit } = setup(true);
  fireEvent.change(box, { target: { value: "Another?" } });
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(onSubmit).not.toHaveBeenCalled();
});
