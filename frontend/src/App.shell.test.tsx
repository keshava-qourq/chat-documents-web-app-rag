import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App shell", () => {
  it("makes chat and documents reachable from the nav, with no setup tab", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <App />
      </MemoryRouter>,
    );
    const nav = screen.getByLabelText("Main navigation");
    expect(within(nav).getByText("Chat")).toBeInTheDocument();
    expect(within(nav).getByText("Documents")).toBeInTheDocument();
    expect(within(nav).queryByText("Setup & status")).not.toBeInTheDocument();
  });

  it("keeps the chat panel mounted (not torn down) after a round trip to Documents", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("chat-panel")).not.toHaveAttribute("hidden");
    expect(screen.queryByTestId("documents-panel")).not.toBeInTheDocument();

    const nav = screen.getByLabelText("Main navigation");
    await user.click(within(nav).getByText("Documents"));

    // Chat panel stays in the DOM (just hidden) rather than unmounting --
    // this is what keeps its open thread's in-memory state intact (AC-058).
    expect(screen.getByTestId("chat-panel")).toHaveAttribute("hidden");
    expect(screen.getByTestId("documents-panel")).not.toHaveAttribute("hidden");

    await user.click(within(screen.getByLabelText("Main navigation")).getByText("Chat"));

    expect(screen.getByTestId("chat-panel")).not.toHaveAttribute("hidden");
    // Documents panel is still mounted too, just hidden -- never torn down.
    expect(screen.getByTestId("documents-panel")).toHaveAttribute("hidden");
  });

  it("offers a mobile menu toggle that opens and closes a nav drawer", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <App />
      </MemoryRouter>,
    );

    const toggle = screen.getByLabelText("Open navigation menu");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("nav-drawer-scrim")).not.toBeInTheDocument();

    await user.click(toggle);

    expect(screen.getByLabelText("Close navigation menu")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("nav-drawer-scrim")).toBeInTheDocument();

    await user.click(screen.getByTestId("nav-drawer-scrim"));
    expect(screen.getByLabelText("Open navigation menu")).toHaveAttribute("aria-expanded", "false");
  });

  it("redirects an unknown route to chat without any login gate", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("chat-panel")).not.toHaveAttribute("hidden");
    expect(screen.queryByText(/log in/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/sign up/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/password/i)).not.toBeInTheDocument();
  });
});
