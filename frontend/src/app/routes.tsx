import { lazy } from "react";
import { Route, Routes } from "react-router";
import { AppShell } from "./AppShell";

// Every page is its own chunk; the shell and providers are the only eager code.
const Home = lazy(() => import("../pages/Home").then((m) => ({ default: m.Home })));
const Conversation = lazy(() => import("../pages/Conversation").then((m) => ({ default: m.Conversation })));
const Settings = lazy(() => import("../pages/Settings").then((m) => ({ default: m.Settings })));
const HowItWorks = lazy(() => import("../pages/HowItWorks").then((m) => ({ default: m.HowItWorks })));
const NotFound = lazy(() => import("../pages/NotFound").then((m) => ({ default: m.NotFound })));
// Dev builds only: the condition is a constant false in production, so the chunk is never emitted.
const Styleguide = import.meta.env.DEV
  ? lazy(() => import("../design/styleguide/Styleguide").then((m) => ({ default: m.Styleguide })))
  : null;

/** The route table (DESIGN_V2 "Information architecture"; later milestones add the rest). */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Home />} />
        <Route path="ask" element={<Conversation />} />
        <Route path="settings" element={<Settings />} />
        <Route path="how-it-works" element={<HowItWorks />} />
        {Styleguide && <Route path="styleguide" element={<Styleguide />} />}
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
