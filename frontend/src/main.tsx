import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./design/design.css";
import "./design/fonts";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
