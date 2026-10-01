import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { messages } from "../i18n/messages.ts";
import { ApiError } from "../lib/api/errors.ts";
import { shouldRetryQuery } from "./providers.tsx";
import { routes } from "./router.tsx";

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
  return router;
}

beforeEach(() => {
  // Phone-sized viewport (design target 360x640).
  window.innerWidth = 360;
  window.innerHeight = 640;
});

describe("AppShell", () => {
  it("renders the header, main landmark and landing text from the catalog", () => {
    renderAt("/");

    const banner = screen.getByRole("banner");
    expect(within(banner).getByRole("link", { name: messages["app.name"] })).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(
      within(main).getByRole("heading", { level: 1, name: messages["home.title"] }),
    ).toBeInTheDocument();
    expect(within(main).getByText(messages["home.body"])).toBeInTheDocument();
  });

  it("offers a skip link that targets the main content", async () => {
    renderAt("/");
    const user = userEvent.setup();

    await user.tab();
    const skip = screen.getByRole("link", { name: messages["app.skipToContent"] });
    expect(skip).toHaveFocus();
    expect(skip).toHaveAttribute("href", `#${screen.getByRole("main").id}`);
  });

  it("uses touch targets of at least 44px for header links", () => {
    renderAt("/");
    const home = within(screen.getByRole("banner")).getByRole("link");
    // min-h-11 / min-w-11 = 2.75rem = 44px in Tailwind's default scale.
    expect(home.className).toMatch(/\bmin-h-11\b/);
    expect(home.className).toMatch(/\bmin-w-11\b/);
  });

  it("shows a not-found page with a way home for unknown routes", async () => {
    const router = renderAt("/does-not-exist");
    expect(
      screen.getByRole("heading", { level: 1, name: messages["notFound.title"] }),
    ).toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole("link", { name: messages["notFound.action"] }));
    expect(router.state.location.pathname).toBe("/");
    expect(screen.getByRole("heading", { name: messages["home.title"] })).toBeInTheDocument();
  });

  it("shows the route-error page without error details when a child route throws", () => {
    const canary = "CANARY-route-error-detail-0003";
    function Boom(): never {
      throw new Error(canary);
    }
    // Reuse the real root route's shell and errorElement; swap in a throwing child.
    const [root] = routes;
    if (!root) throw new Error("routes table is empty");
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: root.element,
          errorElement: root.errorElement,
          children: [{ path: "boom", element: <Boom /> }],
        },
      ],
      { initialEntries: ["/boom"] },
    );
    // React and the router log the caught error; keep test output clean.
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      render(<RouterProvider router={router} />);

      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { level: 1, name: messages["routeError.title"] }),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: messages["routeError.action"] })).toHaveAttribute(
        "href",
        "/",
      );
      expect(document.body.textContent).not.toContain(canary);
    } finally {
      consoleError.mockRestore();
    }
  });
});

describe("shouldRetryQuery", () => {
  const err = (status: number) => new ApiError({ status, code: "x", message: "x" });

  it("retries network failures and 5xx up to the limit", () => {
    expect(shouldRetryQuery(0, err(0))).toBe(true);
    expect(shouldRetryQuery(1, err(503))).toBe(true);
    expect(shouldRetryQuery(2, err(503))).toBe(false);
  });

  it("never retries 4xx or unknown errors", () => {
    expect(shouldRetryQuery(0, err(400))).toBe(false);
    expect(shouldRetryQuery(0, err(401))).toBe(false);
    expect(shouldRetryQuery(0, err(404))).toBe(false);
    expect(shouldRetryQuery(0, new Error("x"))).toBe(false);
  });
});
