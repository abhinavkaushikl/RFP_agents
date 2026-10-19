import "./styles/index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { lazy, StrictMode, Suspense, type ComponentType } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { reloadForUpdate, RouteError } from "@/components/RouteError";
import { ToastProvider } from "@/components/Toast";
import { ProfileProvider } from "@/hooks/useProfile";
import { ThemeProvider } from "@/hooks/useTheme";
import { ApiError } from "@/lib/api";

const Home = lazy(() => import("@/pages/Home"));
const Proposals = lazy(() => import("@/pages/Proposals"));
const NewProposal = lazy(() => import("@/pages/NewProposal"));
const Workspace = lazy(() => import("@/pages/Workspace"));
const DealAnalysis = lazy(() => import("@/pages/DealAnalysis"));
const BidCheck = lazy(() => import("@/pages/BidCheck"));
const MarketScan = lazy(() => import("@/pages/MarketScan"));
const KnowledgeBase = lazy(() => import("@/pages/KnowledgeBase"));
const Usage = lazy(() => import("@/pages/Usage"));
const Settings = lazy(() => import("@/pages/Settings"));
const NotFound = lazy(() => import("@/pages/NotFound"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => count < 1 && !(err instanceof ApiError && err.status >= 400 && err.status < 500),
    },
  },
});

const page = (Component: ComponentType) => (
  <Suspense fallback={<div className="p-8" />}>
    <Component />
  </Suspense>
);

// A tab opened before a deployment may ask for page files that no longer exist; reload once to get the new build.
window.addEventListener("vite:preloadError", (event) => {
  if (reloadForUpdate()) event.preventDefault();
});

const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteError fullPage />,
    children: [
      {
        // Page errors render inside the shell, so navigation stays usable.
        errorElement: <RouteError />,
        children: [
          { index: true, element: page(Home) },
          { path: "proposals", element: page(Proposals) },
          { path: "proposals/:id", element: page(Workspace) },
          { path: "new", element: page(NewProposal) },
          { path: "deals", element: page(DealAnalysis) },
          { path: "bid-check", element: page(BidCheck) },
          { path: "market", element: page(MarketScan) },
          { path: "library", element: page(KnowledgeBase) },
          { path: "usage", element: page(Usage) },
          { path: "settings", element: page(Settings) },
          { path: "*", element: page(NotFound) },
        ],
      },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ProfileProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </ProfileProvider>
      </QueryClientProvider>
      </ThemeProvider>
    </MotionConfig>
  </StrictMode>,
);
