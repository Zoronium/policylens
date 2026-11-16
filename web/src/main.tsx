import "@fontsource-variable/source-serif-4";
import "@fontsource-variable/public-sans";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./stageshow/kit/stageshow.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
