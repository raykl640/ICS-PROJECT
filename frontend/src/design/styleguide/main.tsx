import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../design.css";
import "../fonts";
import { Styleguide } from "./Styleguide";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Styleguide />
  </StrictMode>,
);
