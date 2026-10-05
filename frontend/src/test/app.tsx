import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { Providers } from "../app/Providers";
import { AppRoutes } from "../app/routes";

/** The whole app (providers, shell, lazy routes) at a path, as after a page load. */
export function renderApp(path = "/") {
  return render(
    <Providers>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </Providers>,
  );
}
