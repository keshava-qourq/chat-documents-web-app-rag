// Unit tests for `app/lib/icons.tsx`.
//
// This module is the entire icon set generated screens may draw from --
// deliberately finite, deliberately hand-drawn, with no bundler to fall back
// on. The risk that actually breaks a screen is not "does Plus look right"
// (nobody here can judge that) but: does every name a screen reaches for
// still resolve to a real component, does each render a real, visible <svg>
// rather than an empty shell, does the `size` prop actually size it, and do
// caller-supplied props (className, aria-hidden overrides) still reach the
// DOM. Every name referenced from App.tsx, Setup.tsx and Documents.tsx is
// checked explicitly so that removing one from the set is a failing test
// here, not a blank square discovered on screen.
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ICON_NAMES, Icons } from "./icons";

// Every icon name actually referenced via `Icons.<Name>` elsewhere in the
// app (App.tsx, Setup.tsx, Documents.tsx) at the time this test was written.
const NAMES_USED_BY_SCREENS = [
  "Plus",
  "Search",
  "Check",
  "X",
  "ChevronRight",
  "Menu",
  "Settings",
  "FileText",
  "Trash",
  "Upload",
  "ArrowRight",
  "AlertCircle",
  "CheckCircle",
  "Clock",
  "Users",
];

describe("ICON_NAMES", () => {
  it("lists every name screens currently draw on, with no duplicates", () => {
    for (const name of NAMES_USED_BY_SCREENS) {
      expect(ICON_NAMES).toContain(name);
    }
    expect(new Set(ICON_NAMES).size).toBe(ICON_NAMES.length);
  });

  it("has a component in Icons for every name it lists, and nothing extra", () => {
    expect(Object.keys(Icons).sort()).toEqual([...ICON_NAMES].sort());
  });
});

describe("Icons.<Name> components", () => {
  it("renders a real svg element with visible path content for every registered icon", () => {
    for (const name of ICON_NAMES) {
      const Icon = Icons[name];
      const { container, unmount } = render(<Icon data-testid="icon" />);
      const svg = container.querySelector("svg");
      expect(svg, `${name} should render an <svg>`).not.toBeNull();
      // Every icon must draw something -- an entry with no path/circle body
      // is a blank square on screen even though the element exists.
      expect(
        svg!.querySelectorAll("path, circle, rect").length,
        `${name} should draw at least one shape`,
      ).toBeGreaterThan(0);
      unmount();
    }
  });

  it("defaults to a 16x16 box and scales with the size prop", () => {
    const { container: defaultContainer } = render(<Icons.Plus />);
    const defaultSvg = defaultContainer.querySelector("svg")!;
    expect(defaultSvg.getAttribute("width")).toBe("16");
    expect(defaultSvg.getAttribute("height")).toBe("16");

    const { container: sizedContainer } = render(<Icons.Plus size={32} />);
    const sizedSvg = sizedContainer.querySelector("svg")!;
    expect(sizedSvg.getAttribute("width")).toBe("32");
    expect(sizedSvg.getAttribute("height")).toBe("32");
  });

  it("is hidden from assistive tech by default, as a decorative icon should be", () => {
    const { container } = render(<Icons.Check />);
    expect(container.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
  });

  it("forwards arbitrary svg props such as className and an explicit aria-hidden override", () => {
    const { container } = render(
      <Icons.AlertCircle className="h-4 w-4 text-red-500" aria-hidden="false" />,
    );
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("class")).toContain("h-4 w-4 text-red-500");
    // A caller passing an explicit prop (e.g. to expose a meaningful icon to
    // a screen reader) must be able to override the component's default.
    expect(svg.getAttribute("aria-hidden")).toBe("false");
  });

  it("gives each icon its own distinct path data, rather than silently sharing one shape", () => {
    const shapesFor = (name: string) => {
      const { container } = render(Icons[name]({}));
      return container.innerHTML;
    };
    expect(shapesFor("Plus")).not.toEqual(shapesFor("X"));
    expect(shapesFor("ChevronLeft")).not.toEqual(shapesFor("ChevronRight"));
  });
});
