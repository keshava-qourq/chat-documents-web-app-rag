// Coverage for `app/lib/icons.tsx` -- the hand-drawn, finite icon set the
// Builder prompt names. There was no other seam exercising this module
// directly: generated screens import `Icons.SomeName` and render it, so a
// typo in a `d` attribute, a size prop that stops working, or a name quietly
// dropped from the set would otherwise only surface as a blank square on a
// generated screen, if anyone noticed at all.
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Icons, ICON_NAMES } from "./icons";

// The exact vocabulary the Builder prompt lists. This is deliberately a
// literal list, not a derived one -- the point of the test is to fail if a
// name is added, renamed or removed without the prompt (and every screen
// that might use it) being updated to match.
const EXPECTED_NAMES = [
  "Plus",
  "Search",
  "Check",
  "X",
  "ChevronRight",
  "ChevronLeft",
  "ChevronDown",
  "Menu",
  "User",
  "Users",
  "Settings",
  "Bell",
  "Home",
  "FileText",
  "Package",
  "Calendar",
  "Clock",
  "Trash",
  "Edit",
  "Filter",
  "Download",
  "Upload",
  "ArrowLeft",
  "ArrowRight",
  "AlertCircle",
  "CheckCircle",
  "MoreHorizontal",
];

describe("ICON_NAMES — the finite set", () => {
  it("lists exactly the names the Builder prompt promises, no more and no fewer", () => {
    expect([...ICON_NAMES].sort()).toEqual([...EXPECTED_NAMES].sort());
  });

  it("has a component registered under Icons for every name it lists", () => {
    for (const name of ICON_NAMES) {
      expect(Icons[name]).toBeTypeOf("function");
    }
  });

  it("has no component registered for a name outside the set", () => {
    expect(Icons.Rocket).toBeUndefined();
    expect(Icons.rocket).toBeUndefined();
  });
});

describe("rendering an icon", () => {
  it("renders an svg with the shared frame: 24x24 viewBox, currentColor stroke, hidden from assistive tech", () => {
    const Plus = Icons.Plus;
    const { getByTestId } = render(<Plus data-testid="icon" />);
    const svg = getByTestId("icon");

    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg).toHaveAttribute("viewBox", "0 0 24 24");
    expect(svg).toHaveAttribute("stroke", "currentColor");
    expect(svg).toHaveAttribute("fill", "none");
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("defaults to a 16x16 box when no size is given", () => {
    const Search = Icons.Search;
    const { getByTestId } = render(<Search data-testid="icon" />);
    const svg = getByTestId("icon");

    expect(svg).toHaveAttribute("width", "16");
    expect(svg).toHaveAttribute("height", "16");
  });

  it("honours an explicit size prop on both width and height", () => {
    const Search = Icons.Search;
    const { getByTestId } = render(<Search data-testid="icon" size={32} />);
    const svg = getByTestId("icon");

    expect(svg).toHaveAttribute("width", "32");
    expect(svg).toHaveAttribute("height", "32");
  });

  it("forwards arbitrary svg props, such as className, onto the element", () => {
    const Check = Icons.Check;
    const { getByTestId } = render(<Check data-testid="icon" className="text-emerald-600" />);
    const svg = getByTestId("icon");

    expect(svg).toHaveClass("text-emerald-600");
  });

  it("keeps aria-hidden true even if a caller tries to override it, so the icon never leaks into the accessibility tree", () => {
    const X = Icons.X;
    const { getByTestId } = render(<X data-testid="icon" aria-hidden="false" />);
    const svg = getByTestId("icon");

    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("draws different geometry for different icons, rather than one shape under every name", () => {
    const { getByTestId: getPlus } = render(<Icons.Plus data-testid="plus" />);
    const { getByTestId: getSearch } = render(<Icons.Search data-testid="search" />);

    expect(getPlus("plus").innerHTML).not.toBe(getSearch("search").innerHTML);
  });

  it("renders every name in the set to a real svg without throwing", () => {
    for (const name of ICON_NAMES) {
      const IconComponent = Icons[name];
      const { getByTestId, unmount } = render(<IconComponent data-testid={`icon-${name}`} />);
      const svg = getByTestId(`icon-${name}`);
      expect(svg.tagName.toLowerCase()).toBe("svg");
      expect(svg.children.length).toBeGreaterThan(0);
      unmount();
    }
  });
});
