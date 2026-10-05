import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Button } from "./Button";
import { CommandPalette } from "./CommandPalette";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "./Dialog";
import { Field } from "./Field";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "./Menu";
import { Popover, PopoverContent, PopoverTrigger, Tooltip, TooltipProvider } from "./Overlay";
import { ProgressSteps } from "./ProgressSteps";
import { Masthead } from "./Shell";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./Tabs";
import { ToastProvider } from "./Toast";
import { useToast } from "./toastContext";
import { ToggleGroup } from "./ToggleGroup";

describe("Dialog", () => {
  function Example() {
    return (
      <Dialog>
        <DialogTrigger asChild>
          <Button>Open</Button>
        </DialogTrigger>
        <DialogContent title="Delete this chat?" closeLabel="Close">
          <DialogClose asChild>
            <Button>Cancel</Button>
          </DialogClose>
          <Button variant="danger">Delete</Button>
        </DialogContent>
      </Dialog>
    );
  }

  it("traps focus while open and Escape closes it, returning focus to the trigger", async () => {
    const user = userEvent.setup();
    render(<Example />);
    const trigger = screen.getByRole("button", { name: "Open" });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Delete this chat?" });
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    for (let i = 0; i < 5; i++) {
      await user.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
    await user.tab({ shift: true });
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("closes from the named close button", async () => {
    const user = userEvent.setup();
    render(<Example />);
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("Menu", () => {
  it("opens from the keyboard, arrows move between items, Escape closes and returns focus", async () => {
    const user = userEvent.setup();
    const onRename = vi.fn();
    render(
      <Menu>
        <MenuTrigger asChild>
          <Button>Actions</Button>
        </MenuTrigger>
        <MenuContent>
          <MenuItem onSelect={onRename}>Rename</MenuItem>
          <MenuItem>Duplicate</MenuItem>
          <MenuItem tone="danger">Delete</MenuItem>
        </MenuContent>
      </Menu>,
    );
    const trigger = screen.getByRole("button", { name: "Actions" });
    trigger.focus();
    await user.keyboard("{Enter}");
    const menu = await screen.findByRole("menu");
    const items = within(menu).getAllByRole("menuitem");
    await waitFor(() => expect(items[0]).toHaveFocus());
    await user.keyboard("{ArrowDown}");
    expect(items[1]).toHaveFocus();
    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(items[0]).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(items[2]).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getAllByRole("menuitem")[0]).toHaveFocus());
    await user.keyboard("{Enter}");
    expect(onRename).toHaveBeenCalledOnce();
  });
});

describe("Tabs", () => {
  it("arrow keys, Home and End move focus and selection", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="a">
        <TabsList aria-label="Answer">
          <TabsTrigger value="a">Rights</TabsTrigger>
          <TabsTrigger value="b">Steps</TabsTrigger>
          <TabsTrigger value="c">Letter</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Panel A</TabsContent>
        <TabsContent value="b">Panel B</TabsContent>
        <TabsContent value="c">Panel C</TabsContent>
      </Tabs>,
    );
    const [a, b, c] = screen.getAllByRole("tab");
    await user.click(a);
    await user.keyboard("{ArrowRight}");
    expect(b).toHaveFocus();
    expect(b).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel B");
    await user.keyboard("{End}");
    expect(c).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(a).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(c).toHaveFocus();
    await user.keyboard("{Home}");
    expect(a).toHaveAttribute("aria-selected", "true");
  });
});

describe("ToggleGroup", () => {
  function Example({ onChange }: { onChange: (v: string) => void }) {
    const [value, setValue] = useState<"en" | "sw">("en");
    return (
      <ToggleGroup
        label="Answer language"
        value={value}
        onValueChange={(v) => {
          setValue(v);
          onChange(v);
        }}
        items={[
          { value: "en", label: "English" },
          { value: "sw", label: "Kiswahili" },
        ]}
      />
    );
  }

  it("arrows move focus, Space picks, and the selected item cannot be cleared", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Example onChange={onChange} />);
    expect(screen.getByRole("radiogroup", { name: "Answer language" })).toBeInTheDocument();
    const en = screen.getByRole("radio", { name: "English" });
    const sw = screen.getByRole("radio", { name: "Kiswahili" });
    await user.click(en);
    expect(en).toBeChecked();
    expect(onChange).not.toHaveBeenCalled();
    await user.keyboard("{ArrowRight}");
    expect(sw).toHaveFocus();
    await user.keyboard(" ");
    expect(sw).toBeChecked();
    expect(onChange).toHaveBeenLastCalledWith("sw");
  });
});

describe("CommandPalette", () => {
  function Example({ onPick }: { onPick: (id: string) => void }) {
    const [open, setOpen] = useState(true);
    return (
      <CommandPalette
        open={open}
        onOpenChange={setOpen}
        title="Search and commands"
        placeholder="Type to search"
        emptyText="Nothing matches."
        items={["Lorem", "Ipsum", "Dolor", "Dolorem"].map((label) => ({
          id: label.toLowerCase(),
          label,
          group: label.startsWith("D") ? "Laws" : "Navigate",
          onSelect: () => onPick(label),
        }))}
      />
    );
  }

  it("filters as you type, arrows move the active option, Enter runs it and closes", async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(<Example onPick={onPick} />);
    const input = screen.getByRole("combobox", { name: "Search and commands" });
    await waitFor(() => expect(input).toHaveFocus());
    await user.keyboard("dol");
    const options = screen.getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["Dolor", "Dolorem"]);
    expect(input).toHaveAttribute("aria-activedescendant", options[0].id);
    await user.keyboard("{ArrowDown}");
    expect(options[1]).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowDown}");
    expect(input).toHaveAttribute("aria-activedescendant", options[0].id);
    await user.keyboard("{ArrowUp}{Enter}");
    expect(onPick).toHaveBeenCalledWith("Dolorem");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("says so when nothing matches", async () => {
    const user = userEvent.setup();
    render(<Example onPick={() => {}} />);
    await user.keyboard("zzz{Enter}");
    expect(screen.getByText("Nothing matches.")).toBeInTheDocument();
    expect(screen.queryAllByRole("option")).toEqual([]);
  });
});

describe("Tooltip and Popover", () => {
  it("tooltip shows on keyboard focus", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip label="Copy citation">
          <Button>Copy</Button>
        </Tooltip>
      </TooltipProvider>,
    );
    await user.tab();
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Copy citation");
  });

  it("popover opens from its trigger and Escape returns focus", async () => {
    const user = userEvent.setup();
    render(
      <Popover>
        <PopoverTrigger asChild>
          <Button>Contents</Button>
        </PopoverTrigger>
        <PopoverContent aria-label="Contents">
          <a href="#x">Lorem</a>
        </PopoverContent>
      </Popover>,
    );
    const trigger = screen.getByRole("button", { name: "Contents" });
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "Contents" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});

describe("Toast", () => {
  function Example() {
    const toast = useToast();
    return <Button onClick={() => toast({ title: "Your answer is ready", tone: "success" })}>Notify</Button>;
  }

  it("announces a toast that can be dismissed by its close button", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider closeLabel="Dismiss" regionLabel="Notifications">
        <Example />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "Notify" }));
    expect(screen.getAllByText("Your answer is ready").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument());
  });
});

describe("own components", () => {
  it("Field wires label, hint and error", () => {
    render(<Field label="Phone number" hint="Ten digits." error="Too short." />);
    const input = screen.getByRole("textbox", { name: "Phone number" });
    expect(input).toHaveAccessibleDescription("Ten digits. Too short.");
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("Masthead marks the current page and opens the palette from the search button", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(
      <Masthead
        label="Main"
        brand={<a href="#top">Brand</a>}
        items={[
          { id: "h", label: "Home", icon: null, href: "#h", current: true },
          { id: "l", label: "Laws", icon: null, href: "#l" },
        ]}
        search={{ label: "Search pages", short: "Search", shortcut: "Ctrl K", onOpen }}
        end={<button type="button">Account</button>}
      />,
    );
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Laws" })).not.toHaveAttribute("aria-current");
    await user.click(screen.getByRole("button", { name: /Search/ }));
    expect(onOpen).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Account" })).toBeInTheDocument();
  });

  it("ProgressSteps marks the current step and reads each status", () => {
    render(
      <ProgressSteps
        label="Answer progress"
        statusText={{ done: "done", current: "in progress", todo: "waiting" }}
        steps={[
          { label: "Searching", status: "done" },
          { label: "Writing", status: "current" },
          { label: "Checking", status: "todo" },
        ]}
      />,
    );
    const items = within(screen.getByRole("list", { name: "Answer progress" })).getAllByRole("listitem");
    expect(items[1]).toHaveAttribute("aria-current", "step");
    expect(items.map((i) => i.textContent)).toEqual(["Searching, done", "Writing, in progress", "Checking, waiting"]);
  });
});
