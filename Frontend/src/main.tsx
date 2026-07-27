import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { SettingsSynchronizer } from "./components/shared/SettingsSynchronizer";
import { queryClient } from "./lib/query-client";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("EyeAI root element was not found.");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <SettingsSynchronizer />
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
