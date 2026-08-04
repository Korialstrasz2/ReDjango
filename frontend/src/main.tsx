import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, useLocation } from "react-router-dom";

import { App } from "./App";
import { MasterAILauncherRuntime } from "./features/master-ai/launchers";
import { MasterAIRoot } from "./features/master-ai/MasterAIRoot";
import { ThemeRevealRuntime } from "./features/theme/ThemeRevealRuntime";
import "./styles/app.css";
import "./styles/theme-reveal.css";
import "./styles/master-ai.css";
import "./styles/master-ai-launchers.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: 0 }
  }
});

function RootApplication() {
  const location = useLocation();
  const masterAIPath = location.pathname === "/tools/master-ai" || location.pathname.startsWith("/tools/master-ai/");
  return <><ThemeRevealRuntime /><MasterAILauncherRuntime />{masterAIPath ? <MasterAIRoot /> : <App />}</>;
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