import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import Screen from "./Setup";

function renderScreen() {
  return render(
    <MemoryRouter>
      <Screen />
    </MemoryRouter>,
  );
}

describe("Setup screen — static operator documentation (AC-065..070)", () => {
  it("renders without throwing and states it is static documentation, not a live status page", () => {
    renderScreen();
    expect(screen.getByRole("heading", { name: "Setup & status" })).toBeInTheDocument();
    expect(screen.getByText(/calls no API and polls nothing/i)).toBeInTheDocument();
  });

  it("lists exactly the environment variables the backend reads, with documented defaults (AC-065)", () => {
    renderScreen();
    const expected = [
      "GEMINI_API_KEY",
      "DATABASE_URL",
      "MINIO_ENDPOINT",
      "MINIO_ACCESS_KEY",
      "MINIO_SECRET_KEY",
      "MINIO_BUCKET",
      "DOCUMENT_CAP",
      "RATE_LIMIT_CHAT_PER_MIN",
      "RATE_LIMIT_UPLOADS_PER_HOUR",
    ];
    for (const envVar of expected) {
      expect(screen.getByText(envVar)).toBeInTheDocument();
    }
    expect(screen.getByText(/^Default: documents$/)).toBeInTheDocument();
    expect(screen.getByText(/^Default: 200$/)).toBeInTheDocument();
    expect(screen.getByText(/^Default: 20$/)).toBeInTheDocument();
    expect(screen.getByText(/^Default: 10$/)).toBeInTheDocument();

    // No longer reference npm run db:push, npm start, or a Node-only single process.
    expect(screen.queryByText(/db:push/)).not.toBeInTheDocument();
    expect(screen.queryByText(/npm start/)).not.toBeInTheDocument();
    expect(screen.queryByText(/one process/i)).not.toBeInTheDocument();
  });

  it("describes the delivered stack's run and deploy instructions (AC-065/AC-066)", async () => {
    const user = userEvent.setup();
    renderScreen();

    // Local run instructions, visible by default.
    expect(screen.getByText(/cp \.env\.example \.env/)).toBeInTheDocument();
    expect(screen.getByText(/docker compose up -d/)).toBeInTheDocument();
    expect(screen.getByText(/pip install -r requirements\.txt/)).toBeInTheDocument();
    expect(screen.getByText(/uvicorn app\.main:app --reload/)).toBeInTheDocument();
    expect(screen.getByText(/npm run dev/)).toBeInTheDocument();

    // Deploy tab.
    await user.click(screen.getByRole("tab", { name: "Deploy it" }));
    expect(screen.getAllByText(/npm run build/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/uvicorn app\.main:app --host/).length).toBeGreaterThan(0);
  });

  it("never renders a key value and states the key is server-side only (AC-068)", () => {
    renderScreen();
    expect(screen.queryByText(/••••/)).not.toBeInTheDocument();
    expect(screen.queryByText(/AIza/)).not.toBeInTheDocument();
    expect(screen.getByText(/GEMINI_API_KEY is never shown here/i)).toBeInTheDocument();
    expect(screen.getAllByText(/no endpoint in this app returns it/i).length).toBeGreaterThan(0);
  });

  it("matches the backend's actual missing/invalid key messages, naming GEMINI_API_KEY (AC-067)", async () => {
    const user = userEvent.setup();
    renderScreen();
    await user.click(screen.getByRole("tab", { name: "When it goes wrong" }));
    expect(screen.getByText(/Gemini is not configured\./)).toBeInTheDocument();
    expect(screen.getByText(/The answer generation service is unavailable\./)).toBeInTheDocument();
    expect(screen.getAllByText(/GEMINI_API_KEY/).length).toBeGreaterThan(0);
  });

  it("contains no pricing, paywall UI, subscription or upgrade affordance (AC-069)", () => {
    renderScreen();
    // The footer disclaims these by name (AC-070) -- that sentence is required
    // copy, not a feature. What must not exist is any pricing table, quota
    // purchase control, or button offering to subscribe/upgrade/pay.
    expect(screen.queryByText(/pricing/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/subscription/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/upgrade/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /upgrade|subscribe|buy|purchase|pay/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /upgrade|subscribe|buy|purchase|pay/i })).not
      .toBeInTheDocument();
  });

  it("states Gemini usage bills the operator's own Google account and the app bills no one (AC-070)", () => {
    renderScreen();
    expect(
      screen.getByText(/Gemini usage for\s+answers and embeddings is charged to the operator/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/this app bills no one/i)).toBeInTheDocument();
    expect(screen.getByText(/No plans, no paywall and no usage billing/i)).toBeInTheDocument();
  });
});
