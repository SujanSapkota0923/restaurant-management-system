import { useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";
import { AppProviders } from "./providers.tsx";
import { routes } from "./router.tsx";

export function App() {
  const [router] = useState(() => createBrowserRouter(routes));
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
