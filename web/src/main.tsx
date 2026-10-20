import "./styles/index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { lazy, StrictMode, Suspense, type ComponentType } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider, useLocation } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { reloadForUpdate, RouteError } from "@/components/RouteError";
import { ToastProvider } from "@/components/Toast";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { ProfileProvider } from "@/hooks/useProfile";
import { ThemeProvider } from "@/hooks/useTheme";
import { ApiError } from "@/lib/api";

const Login = lazy(() => import("@/pages/Login"));
const pageLoaders = {
  Home: () => import("@/pages/Home"),
  Proposals: () => import("@/pages/Proposals"),
  NewProposal: () => import("@/pages/NewProposal"),
  Workspace: () => import("@/pages/Workspace"),
  DealAnalysis: () => import("@/pages/DealAnalysis"),
  BidCheck: () => import("@/pages/BidCheck"),
  MarketScan: () => import("@/pages/MarketScan"),
  KnowledgeBase: () => import("@/pages/KnowledgeBase"),
  Usage: () => import("@/pages/Usage"),
  Settings: () => import("@/pages/Settings"),
};
const Home = lazy(pageLoaders.Home);
const Proposals = lazy(pageLoaders.Proposals);
const NewProposal = lazy(pageLoaders.NewProposal);
const Workspace = lazy(pageLoaders.Workspace);
const DealAnalysis = lazy(pageLoaders.DealAnalysis);
const BidCheck = lazy(pageLoaders.BidCheck);
const MarketScan = lazy(pageLoaders.MarketScan);
const KnowledgeBase = lazy(pageLoaders.KnowledgeBase);
const Usage = lazy(pageLoaders.Usage);
const Settings = lazy(pageLoaders.Settings);

// Fetch the other pages once the browser is idle, so moving between them never waits on a download.
const whenIdle = (window as Window & { requestIdleCallback?: (cb: () => void) => number }).requestIdleCallback;
(whenIdle ?? ((cb: () => void) => window.setTimeout(cb, 2500)))(() => {
  for (const load of Object.values(pageLoaders)) void load();
});
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

/** Sends signed-out visitors to /login when the server requires an account. */
function RequireAuth() {
  const { ready, user, authRequired } = useAuth();
  const location = useLocation();
  if (!ready) return <div className="min-h-dvh bg-canvas" />;
  if (authRequired && !user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <AppShell />;
}

const router = createBrowserRouter([
  { path: "login", element: page(Login) },
  {
    element: <RequireAuth />,
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
        <AuthProvider>
          <ProfileProvider>
            <ToastProvider>
              <RouterProvider router={router} />
            </ToastProvider>
          </ProfileProvider>
        </AuthProvider>
      </QueryClientProvider>
      </ThemeProvider>
    </MotionConfig>
  </StrictMode>,
);
