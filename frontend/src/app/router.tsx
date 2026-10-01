import type { RouteObject } from "react-router";
import { AppShell } from "./AppShell.tsx";
import { HomePage, NotFoundPage, RouteErrorPage } from "./pages.tsx";

/** Route table. Tenant routes (`/r/:tenantId/...`, docs/conventions/api.md) arrive with 0008. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
