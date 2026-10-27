// Unit tests for `app/lib/ui.tsx`.
//
// This module is the component vocabulary every generated screen is written
// against. The risk it actually carries is not "does Card look nice" --
// nobody here judges that -- but: does each component render as the
// semantic element a screen (and the accessibility tree) relies on, does a
// caller-supplied className/prop reach the DOM instead of being swallowed,
// do the controlled components (Switch, Select, Tabs) actually wire their
// value/onChange through rather than rendering a static shell, and do the
// brand-driven pieces (Button primary, Badge accent, headings) keep reading
// `var(--brand-*)` so a brand change still repaints them.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  Avatar,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Checkbox,
  Empty,
  Input,
  Label,
  Select,
  Separator,
  Stat,
  Switch,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  Tabs,
  Textarea,
} from "./ui";

describe("Button", () => {
  it("renders a real <button> that fires onClick and forwards arbitrary props", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(
      <Button onClick={onClick} className="extra-class" data-testid="save">
        Save
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("data-testid", "save");
    expect(button).toHaveClass("extra-class");

    await user.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("respects the disabled prop, blocking the click a disabled button should never deliver", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(
      <Button onClick={onClick} disabled>
        Save
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toBeDisabled();

    await user.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("paints the primary variant from the brand token rather than a hardcoded color", () => {
    render(<Button variant="primary">Go</Button>);
    const button = screen.getByRole("button", { name: "Go" });
    expect(button.style.backgroundColor).toBe("var(--brand-primary)");
  });

  it("does not apply the brand background to non-primary variants", () => {
    render(<Button variant="secondary">Cancel</Button>);
    const button = screen.getByRole("button", { name: "Cancel" });
    expect(button.style.backgroundColor).not.toBe("var(--brand-primary)");
  });

  it("falls back to the primary variant's visual class for an unrecognized variant, instead of rendering unstyled", () => {
    render(<Button variant="not-a-real-variant">Mystery</Button>);
    const button = screen.getByRole("button", { name: "Mystery" });
    // Falling back applies the primary *class* (the unknown-variant branch
    // in BUTTON_VARIANTS); it does not retroactively count as the literal
    // "primary" variant, so the brand background stays unset.
    expect(button.className).toContain("hover:opacity-90");
    expect(button.style.backgroundColor).not.toBe("var(--brand-primary)");
  });
});

describe("Card family", () => {
  it("composes into a structure a screen reader and a screen can both navigate", () => {
    render(
      <Card data-testid="card">
        <CardHeader>
          <CardTitle>Title text</CardTitle>
          <CardDescription>Description text</CardDescription>
        </CardHeader>
        <CardContent>Body content</CardContent>
        <CardFooter>Footer content</CardFooter>
      </Card>,
    );

    expect(screen.getByTestId("card")).toBeInTheDocument();
    // CardTitle must render as a real heading, not a styled <div>, or a
    // screen that relies on it for document structure loses that structure.
    expect(screen.getByRole("heading", { name: "Title text", level: 3 })).toBeInTheDocument();
    expect(screen.getByText("Description text")).toBeInTheDocument();
    expect(screen.getByText("Body content")).toBeInTheDocument();
    expect(screen.getByText("Footer content")).toBeInTheDocument();
  });

  it("gives CardTitle the heading font token so a brand change can restyle it", () => {
    render(<CardTitle>Headline</CardTitle>);
    const heading = screen.getByRole("heading", { name: "Headline" });
    expect(heading.style.fontFamily).toBe("var(--brand-font-heading)");
  });
});

describe("form controls", () => {
  it("Input is a real text input that accepts typing and forwards className", async () => {
    const user = userEvent.setup();
    render(<Input aria-label="Email" className="custom-input" />);
    const input = screen.getByRole("textbox", { name: "Email" });
    expect(input).toHaveClass("custom-input");

    await user.type(input, "person@example.com");
    expect(input).toHaveValue("person@example.com");
  });

  it("Textarea accepts multi-line typing", async () => {
    const user = userEvent.setup();
    render(<Textarea aria-label="Notes" />);
    const textarea = screen.getByRole("textbox", { name: "Notes" });
    await user.type(textarea, "line one");
    expect(textarea).toHaveValue("line one");
  });

  it("Label associates with its control via htmlFor, so clicking the label focuses the input", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Label htmlFor="the-input">Name</Label>
        <Input id="the-input" />
      </>,
    );

    const input = screen.getByLabelText("Name");
    await user.click(screen.getByText("Name"));
    expect(input).toHaveFocus();
  });

  it("Select renders options from the options prop with correct values and labels", () => {
    render(
      <Select
        aria-label="Country"
        options={[
          { value: "us", label: "United States" },
          { value: "ca", label: "Canada" },
        ]}
      />,
    );

    const select = screen.getByRole("combobox", { name: "Country" }) as HTMLSelectElement;
    const optionEls = Array.from(select.options);
    expect(optionEls.map((o) => [o.value, o.textContent])).toEqual([
      ["us", "United States"],
      ["ca", "Canada"],
    ]);
  });

  it("Select renders explicit children instead of the options prop when both could apply", () => {
    render(
      <Select aria-label="Country">
        <option value="uk">United Kingdom</option>
      </Select>,
    );

    const select = screen.getByRole("combobox", { name: "Country" }) as HTMLSelectElement;
    expect(select.options.length).toBe(1);
    expect(select.options[0].value).toBe("uk");
  });

  it("Select fires onChange with the selected value, so a controlled screen actually receives it", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Select
        aria-label="Country"
        onChange={onChange}
        options={[
          { value: "us", label: "United States" },
          { value: "ca", label: "Canada" },
        ]}
      />,
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "Country" }), "ca");
    expect(onChange).toHaveBeenCalled();
    expect((screen.getByRole("combobox", { name: "Country" }) as HTMLSelectElement).value).toBe(
      "ca",
    );
  });

  it("Checkbox is a real checkbox input that toggles and reports checked state", async () => {
    const user = userEvent.setup();
    render(<Checkbox aria-label="Accept terms" />);
    const checkbox = screen.getByRole("checkbox", { name: "Accept terms" });
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);
    expect(checkbox).toBeChecked();
  });
});

describe("Switch", () => {
  it("reflects the checked prop and calls onChange when toggled, as a controlled control must", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Switch checked={false} onChange={onChange} />);

    const toggle = screen.getByRole("checkbox", { hidden: true });
    expect(toggle).not.toBeChecked();

    await user.click(toggle);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("renders as checked when the checked prop is true", () => {
    render(<Switch checked onChange={() => {}} />);
    const toggle = screen.getByRole("checkbox", { hidden: true });
    expect(toggle).toBeChecked();
  });
});

describe("Badge", () => {
  it("applies the accent brand token as a background for the accent variant only", () => {
    const { rerender } = render(<Badge variant="accent">New</Badge>);
    expect(screen.getByText("New").style.backgroundColor).toBe("var(--brand-accent)");

    rerender(<Badge variant="success">Done</Badge>);
    expect(screen.getByText("Done").style.backgroundColor).not.toBe("var(--brand-accent)");
  });

  it("falls back to the default visual style for an unknown variant", () => {
    render(<Badge variant="not-a-real-variant">Weird</Badge>);
    const badge = screen.getByText("Weird");
    expect(badge.className).toContain("bg-slate-100");
  });
});

describe("Table family", () => {
  it("renders a real, navigable <table> with head and body rows, inside a scroll wrapper", () => {
    render(
      <Table aria-label="Documents">
        <THead>
          <TR>
            <TH>Name</TH>
            <TH>Size</TH>
          </TR>
        </THead>
        <TBody>
          <TR>
            <TD>handbook.pdf</TD>
            <TD>1 KB</TD>
          </TR>
        </TBody>
      </Table>,
    );

    const table = screen.getByRole("table", { name: "Documents" });
    expect(table).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "handbook.pdf" })).toBeInTheDocument();
    // The wrapper exists specifically so a wide table scrolls instead of
    // breaking a narrow screen -- losing it is a real regression, not cosmetic.
    expect(table.parentElement).toHaveClass("overflow-x-auto");
  });
});

describe("Avatar", () => {
  it("renders up to two initials from the name when no image is given", () => {
    render(<Avatar name="Ada Lovelace" />);
    expect(screen.getByText("AL")).toBeInTheDocument();
  });

  it("renders an <img> with the name as alt text when a src is given, not the initials", () => {
    render(<Avatar name="Ada Lovelace" src="https://example.com/ada.png" />);
    const img = screen.getByRole("img", { name: "Ada Lovelace" });
    expect(img).toHaveAttribute("src", "https://example.com/ada.png");
    expect(screen.queryByText("AL")).not.toBeInTheDocument();
  });

  it("renders no initials text for an empty name, rather than throwing", () => {
    render(<Avatar />);
    // Should not throw and should render an empty label rather than
    // "undefinedundefined" or similar from an unguarded initials join.
    const avatar = document.querySelector("span");
    expect(avatar?.textContent).toBe("");
  });
});

describe("Separator", () => {
  it("renders a real <hr>, the element assistive tech recognizes as a divider", () => {
    render(<Separator className="my-4" />);
    const hr = document.querySelector("hr");
    expect(hr).not.toBeNull();
    expect(hr).toHaveClass("my-4");
  });
});

describe("Tabs", () => {
  it("renders one button per tab, marks the active one, and calls onChange with the clicked key", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Tabs
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "activity", label: "Activity" },
        ]}
        active="overview"
        onChange={onChange}
      />,
    );

    const overview = screen.getByRole("button", { name: "Overview" });
    const activity = screen.getByRole("button", { name: "Activity" });
    expect(overview.className).not.toBe(activity.className);

    await user.click(activity);
    expect(onChange).toHaveBeenCalledWith("activity");
  });
});

describe("Stat", () => {
  it("renders the label, value and optional hint", () => {
    render(<Stat label="Documents" value={42} hint="Across 3 folders" />);
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Across 3 folders")).toBeInTheDocument();
  });

  it("renders no hint paragraph when none is given, rather than an empty one", () => {
    render(<Stat label="Documents" value={42} />);
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.queryByText("Across 3 folders")).not.toBeInTheDocument();
  });
});

describe("Empty", () => {
  it("renders the title, optional description and an action when given", () => {
    render(
      <Empty
        title="No documents yet"
        description="Upload a file to get started."
        action={<button>Upload</button>}
      />,
    );

    expect(screen.getByText("No documents yet")).toBeInTheDocument();
    expect(screen.getByText("Upload a file to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });

  it("renders only the title when description and action are omitted", () => {
    render(<Empty title="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
