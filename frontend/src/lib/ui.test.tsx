// Coverage for `app/lib/ui.tsx` -- the quiet component vocabulary every
// generated screen is written against. There was no other seam exercising
// this module directly: screens import `Button`, `Card`, `Select` and so on
// and trust them to forward props, merge classes, and wire brand tokens
// correctly. A regression here (a dropped `...props` spread, a variant that
// silently falls through to nothing, a brand token that stops being read)
// would surface as a broken screen everywhere at once.
//
// These tests deliberately avoid pinning exact Tailwind class strings --
// a restyle that keeps the component working should not fail this file.
// Where the file's own stated contract is "reads from a CSS custom
// property", the test checks for that token, because that *is* the
// behaviour this module exists to provide.
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
  Tabs,
  Textarea,
} from "./ui";

describe("Button", () => {
  it("renders its children, forwards onClick, and respects disabled", async () => {
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

  it("fires onClick when enabled", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(<Button onClick={onClick}>Go</Button>);

    await user.click(screen.getByRole("button", { name: "Go" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("paints the primary variant from the --brand-primary custom property, so a brand swap repaints it without a rebuild", () => {
    render(<Button variant="primary">Primary</Button>);
    const button = screen.getByRole("button", { name: "Primary" });
    expect(button.style.backgroundColor).toBe("var(--brand-primary)");
  });

  it("does not hardcode a background colour for non-primary variants", () => {
    render(<Button variant="secondary">Secondary</Button>);
    const button = screen.getByRole("button", { name: "Secondary" });
    expect(button.style.backgroundColor).toBe("");
  });

  it("falls back to the primary look's classes for an unrecognised variant, rather than rendering unstyled", () => {
    render(
      <>
        <Button variant="not-a-real-variant">Mystery</Button>
        <Button variant="primary">Known</Button>
      </>,
    );
    const mystery = screen.getByRole("button", { name: "Mystery" });
    const known = screen.getByRole("button", { name: "Known" });
    expect(mystery.className).toBe(known.className);
  });

  it("falls back to the medium size for an unrecognised size", () => {
    render(
      <>
        <Button size="not-a-real-size">Mystery</Button>
        <Button size="md">Known</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Mystery" }).className).toBe(
      screen.getByRole("button", { name: "Known" }).className,
    );
  });

  it("merges a caller's className onto the base classes rather than replacing them", () => {
    render(<Button className="my-custom-class">Styled</Button>);
    const button = screen.getByRole("button", { name: "Styled" });
    expect(button).toHaveClass("my-custom-class");
    // base styling is still present -- the custom class was additive
    expect(button.className.trim().split(/\s+/).length).toBeGreaterThan(1);
  });

  it("lets a caller's inline style win over the brand-derived background", () => {
    render(
      <Button variant="primary" style={{ backgroundColor: "red" }}>
        Override
      </Button>,
    );
    expect(screen.getByRole("button", { name: "Override" }).style.backgroundColor).toBe("red");
  });
});

describe("Card family", () => {
  it("assembles a card from header, title, description, content and footer with every child rendered", () => {
    render(
      <Card data-testid="card">
        <CardHeader>
          <CardTitle>Document Library</CardTitle>
          <CardDescription>All uploaded files</CardDescription>
        </CardHeader>
        <CardContent>Body text</CardContent>
        <CardFooter>
          <Button>Action</Button>
        </CardFooter>
      </Card>,
    );

    expect(screen.getByRole("heading", { name: "Document Library" })).toBeInTheDocument();
    expect(screen.getByText("All uploaded files")).toBeInTheDocument();
    expect(screen.getByText("Body text")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Action" })).toBeInTheDocument();
  });

  it("lets CardTitle inherit the brand heading font, so a font swap repaints headings everywhere", () => {
    render(<CardTitle>Heading</CardTitle>);
    const heading = screen.getByRole("heading", { name: "Heading" });
    expect(heading.style.fontFamily).toBe("var(--brand-font-heading)");
  });

  it("merges a caller's className onto Card without dropping it", () => {
    render(<Card data-testid="card" className="col-span-2" />);
    expect(screen.getByTestId("card")).toHaveClass("col-span-2");
  });
});

describe("Form controls", () => {
  it("Input forwards value, placeholder and change events like a native input", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Input placeholder="Search" onChange={onChange} />);

    const input = screen.getByPlaceholderText("Search");
    await user.type(input, "a");
    expect(onChange).toHaveBeenCalled();
  });

  it("Textarea renders as a real textarea and accepts typed text", async () => {
    const user = userEvent.setup();
    render(<Textarea aria-label="Notes" />);
    const textarea = screen.getByLabelText("Notes");
    await user.type(textarea, "hello");
    expect(textarea).toHaveValue("hello");
  });

  it("Label associates with its control via htmlFor, the way a form actually needs", () => {
    render(
      <>
        <Label htmlFor="thing">Thing</Label>
        <Input id="thing" />
      </>,
    );
    expect(screen.getByLabelText("Thing")).toBeInTheDocument();
  });

  it("Checkbox is a real checkbox that toggles on click", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Checkbox aria-label="Agree" onChange={onChange} />);
    const box = screen.getByRole("checkbox", { name: "Agree" });
    expect(box).not.toBeChecked();
    await user.click(box);
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});

describe("Select", () => {
  it("renders an <option> for each entry in the options prop, with matching value and label", () => {
    render(
      <Select
        aria-label="Fruit"
        options={[
          { value: "apple", label: "Apple" },
          { value: "pear", label: "Pear" },
        ]}
      />,
    );
    const select = screen.getByLabelText("Fruit") as HTMLSelectElement;
    const options = Array.from(select.options);
    expect(options.map((o) => o.value)).toEqual(["apple", "pear"]);
    expect(options.map((o) => o.textContent)).toEqual(["Apple", "Pear"]);
  });

  it("renders explicit children instead of the options prop when both are given", () => {
    render(
      <Select aria-label="Fruit" options={[{ value: "apple", label: "Apple" }]}>
        <option value="kiwi">Kiwi</option>
      </Select>,
    );
    const select = screen.getByLabelText("Fruit") as HTMLSelectElement;
    const options = Array.from(select.options);
    expect(options.map((o) => o.value)).toEqual(["kiwi"]);
  });

  it("fires onChange with the newly selected value", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Select
        aria-label="Fruit"
        onChange={onChange}
        options={[
          { value: "apple", label: "Apple" },
          { value: "pear", label: "Pear" },
        ]}
      />,
    );
    await user.selectOptions(screen.getByLabelText("Fruit"), "pear");
    expect(onChange).toHaveBeenCalled();
    expect((screen.getByLabelText("Fruit") as HTMLSelectElement).value).toBe("pear");
  });
});

describe("Switch", () => {
  it("reflects the checked prop onto a real checkbox input", () => {
    render(<Switch checked aria-label="Enabled" />);
    expect(screen.getByRole("checkbox", { hidden: true })).toBeChecked();
  });

  it("invokes onChange when the control is clicked, since it is the only way a user can flip it", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Switch checked={false} onChange={onChange} />);
    await user.click(screen.getByRole("checkbox", { hidden: true }));
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});

describe("Badge", () => {
  it("paints the accent variant from the --brand-accent custom property", () => {
    render(<Badge variant="accent">New</Badge>);
    expect(screen.getByText("New").style.backgroundColor).toBe("var(--brand-accent)");
  });

  it("does not set an inline background colour for a non-accent variant", () => {
    render(<Badge variant="success">Ready</Badge>);
    expect(screen.getByText("Ready").style.backgroundColor).toBe("");
  });

  it("falls back to the default look for an unrecognised variant", () => {
    render(
      <>
        <Badge variant="not-a-real-variant">Mystery</Badge>
        <Badge variant="default">Known</Badge>
      </>,
    );
    expect(screen.getByText("Mystery").className).toBe(screen.getByText("Known").className);
  });
});

describe("Table", () => {
  it("renders standard table semantics so assistive tech sees rows, column headers and cells", () => {
    render(
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Size</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>handbook.pdf</td>
            <td>12 KB</td>
          </tr>
        </tbody>
      </table>,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(2);
    expect(screen.getAllByRole("cell")).toHaveLength(2);
  });
});

describe("Avatar", () => {
  it("derives initials from the first letters of the first two words of the name", () => {
    render(<Avatar name="Jane Doe" />);
    expect(screen.getByText("JD")).toBeInTheDocument();
  });

  it("uses a single initial for a single-word name", () => {
    render(<Avatar name="Cher" />);
    expect(screen.getByText("C")).toBeInTheDocument();
  });

  it("ignores words beyond the first two", () => {
    render(<Avatar name="Jane Quincy Doe" />);
    expect(screen.getByText("JQ")).toBeInTheDocument();
    expect(screen.queryByText("JD")).not.toBeInTheDocument();
  });

  it("renders an image with the name as alt text when a src is given, instead of initials", () => {
    render(<Avatar name="Jane Doe" src="https://example.com/jane.png" />);
    const img = screen.getByRole("img", { name: "Jane Doe" });
    expect(img).toHaveAttribute("src", "https://example.com/jane.png");
    expect(screen.queryByText("JD")).not.toBeInTheDocument();
  });
});

describe("Tabs", () => {
  it("renders a button per tab and calls onChange with the clicked tab's key", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Tabs
        tabs={[
          { key: "all", label: "All" },
          { key: "failed", label: "Failed" },
        ]}
        active="all"
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Failed" }));
    expect(onChange).toHaveBeenCalledWith("failed");
  });
});

describe("Stat", () => {
  it("shows the label and value, and omits the hint paragraph when none is given", () => {
    render(<Stat label="Documents" value={12} />);
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.queryByText(/of 200/)).not.toBeInTheDocument();
  });

  it("shows the hint when one is given", () => {
    render(<Stat label="Documents" value={12} hint="of 200 allowed" />);
    expect(screen.getByText("of 200 allowed")).toBeInTheDocument();
  });
});

describe("Separator", () => {
  it("renders a horizontal rule", () => {
    render(<Separator />);
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });
});

describe("Empty", () => {
  it("renders only the title when no description or action is given", () => {
    render(<Empty title="No documents yet" />);
    expect(screen.getByText("No documents yet")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders the description and action when both are given", () => {
    render(
      <Empty
        title="No documents yet"
        description="Upload a PDF to get started."
        action={<Button>Upload</Button>}
      />,
    );
    expect(screen.getByText("Upload a PDF to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });
});
