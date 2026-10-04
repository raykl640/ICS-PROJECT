import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SOURCES } from "../test/fixtures";
import { renderIn } from "../test/render";
import { AnswerMarkdown } from "./AnswerMarkdown";

test("raw HTML from the model is rendered as inert text", () => {
  const { container } = renderIn(
    <AnswerMarkdown
      text={
        'Hello <script>alert("x")</script> <img src="http://evil/x.png" onerror="alert(1)"> [link](javascript:alert(1))'
      }
      sources={[]}
      onCite={() => {}}
    />,
  );
  expect(container.querySelector("script, img, a, iframe")).toBeNull();
  expect(container).toHaveTextContent('<script>alert("x")</script>');
  expect(container.querySelector("[onerror]")).toBeNull();
});

test("markdown structure is kept", () => {
  const { container } = renderIn(
    <AnswerMarkdown text={"1. **First** step\n2. Second"} sources={[]} onCite={() => {}} />,
  );
  expect(container.querySelectorAll("ol > li")).toHaveLength(2);
  expect(container.querySelector("strong")).toHaveTextContent("First");
});

test("a citation that matches a source is a button reporting its chunk", async () => {
  const onCite = vi.fn();
  renderIn(<AnswerMarkdown text="See (Sample Employment Act, s. 4) and s. 99." sources={SOURCES} onCite={onCite} />);
  const cite = screen.getByRole("button", { name: "Show s. 4 in the sources" });
  await userEvent.click(cite);
  expect(onCite).toHaveBeenCalledWith("sample-employment-act-4");
  expect(screen.getAllByRole("button")).toHaveLength(1);
});
