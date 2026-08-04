import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { MasterAIRoot } from "./features/master-ai/MasterAIRoot";
import { ThemeRevealRuntime } from "./features/theme/ThemeRevealRuntime";
import "./styles/app.css";
import "./styles/theme-reveal.css";
import "./styles/master-ai.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: 0 }
  }
});

const masterAIPath = window.location.pathname === "/tools/master-ai" || window.location.pathname.startsWith("/tools/master-ai/");

createRoot(document.getElementById("app")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeRevealRuntime />
        {masterAIPath ? <MasterAIRoot /> : <App />}
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
