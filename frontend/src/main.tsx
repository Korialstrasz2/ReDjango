import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { MasterAILauncherRuntime } from "./features/master-ai/launchers";
import { ThemeRevealRuntime } from "./features/theme/ThemeRevealRuntime";
import "./styles/app.css";
import "./styles/theme-reveal.css";
import "./styles/master-ai.css";
import "./styles/master-ai-shell.css";
import "./styles/master-ai-launchers.css";
import "./styles/master-ai-unit.css";
import "./styles/mobile.css";
import "./styles/mobile-pages.css";
import "./styles/mobile-lore.css";
import "./styles/mobile-reference-pages.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: 0 }
  }
});

// App owns every routed page, including Master AI, so navigation, layout, and shared providers remain consistent.
function RootApplication() {
  return <><ThemeRevealRuntime /><MasterAILauncherRuntime /><App /></>;
}

createRoot(document.getElementById("app")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <RootApplication />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);