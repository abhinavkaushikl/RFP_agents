import { RefreshCw } from "lucide-react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom";

import { Button } from "./ui";

const RELOAD_KEY = "rfp.reloaded-for-update";

/** True when the browser tried to load a page file from an older build that is no longer on the server. */
export function isStaleBuildError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /dynamically imported module|Importing a module script failed|Failed to fetch dynamically|error loading dynamically/i.test(message);
}

/** Reload once to pick up the new build. Returns false if we already reloaded moments ago (avoids loops). */
export function reloadForUpdate(): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? 0);
    if (Date.now() - last < 10_000) return false;
    sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
  } catch {
    /* storage unavailable: reload anyway */
  }
  window.location.reload();
  return true;
}

export function RouteError({ fullPage = false }: { fullPage?: boolean }) {
  const error = useRouteError();
  const stale = isStaleBuildError(error);
  if (stale && reloadForUpdate()) return null;

  const notFound = isRouteErrorResponse(error) && error.status === 404;
  const title = stale ? "A new version is available" : notFound ? "This page does not exist" : "This screen hit an error";
  const detail = stale
    ? "The app was updated while this tab was open. Reload to continue; nothing you saved is lost."
    : notFound
      ? "The link may be old."
      : error instanceof Error
        ? error.message
        : "Reload the page. If it keeps happening, share the message below with your admin.";

  return (
    <div className={fullPage ? "flex min-h-dvh items-center justify-center bg-canvas px-6" : "mx-auto max-w-[640px] px-8 py-20"}>
      <div className="max-w-[56ch]">
        <h1 className="text-display font-semibold text-ink">{title}</h1>
        <p className="mt-2 text-lead text-ink-2">{detail}</p>
        <div className="mt-6 flex gap-2">
          <Button variant="primary" icon={<RefreshCw className="size-4" />} onClick={() => window.location.reload()}>
            Reload
          </Button>
          {!fullPage && (
            <Link to="/" className="inline-flex h-9 items-center rounded-control px-3.5 text-body text-ink-2 hover:bg-wash hover:text-ink">
              Go to Home
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
