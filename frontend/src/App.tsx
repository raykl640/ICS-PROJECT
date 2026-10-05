import { BrowserRouter } from "react-router";
import { ErrorBoundary } from "./app/ErrorBoundary";
import { Providers } from "./app/Providers";
import { AppRoutes } from "./app/routes";

/** HakiAI v2: settings, session and toasts above a client-side router. */
export function App() {
  return (
    <Providers>
      <ErrorBoundary>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </ErrorBoundary>
    </Providers>
  );
}
