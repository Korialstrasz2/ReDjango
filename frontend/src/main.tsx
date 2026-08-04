import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ThemeRevealRuntime } from "./features/theme/ThemeRevealRuntime";
import "./styles/app.css";
import "./styles/theme-reveal.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: 0 }
  }
});

createRoot(document.getElementById("app")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeRevealRuntime />
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
