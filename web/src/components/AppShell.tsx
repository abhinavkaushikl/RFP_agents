import * as Popover from "@radix-ui/react-popover";
import * as Tooltip from "@radix-ui/react-tooltip";
import clsx from "clsx";
import {
  BarChart3,
  Check,
  ChevronsLeft,
  ChevronsUpDown,
  FilePlus2,
  Files,
  House,
  Library,
  Menu,
  Package,
  MessagesSquare,
  Radar,
  ScanSearch,
  Search,
  LogOut,
  Settings2,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate, useOutlet } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { useProfile } from "@/hooks/useProfile";
import { useReadiness } from "@/hooks/useReadiness";
import { pageVariants, spring } from "@/lib/motion";
import { CommandPalette } from "./CommandPalette";
import { StarField } from "./StarField";
import { ThemeToggle } from "./ThemeToggle";
import { Kbd } from "./ui";

interface NavItem { to: string; label: string; icon: ReactNode; end?: boolean }

export const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Workspace",
    items: [
      { to: "/", label: "Home", icon: <House className="size-[18px]" />, end: true },
      { to: "/proposals", label: "Proposals", icon: <Files className="size-[18px]" /> },
      { to: "/new", label: "New proposal", icon: <FilePlus2 className="size-[18px]" /> },
    ],
  },
  {
    group: "Analyze",
    items: [
      { to: "/deals", label: "Deal analysis", icon: <MessagesSquare className="size-[18px]" /> },
      { to: "/bid-check", label: "Bid check", icon: <ScanSearch className="size-[18px]" /> },
      { to: "/market", label: "Market scan", icon: <Radar className="size-[18px]" /> },
    ],
  },
  {
    group: "Library",
    items: [
      { to: "/solutions", label: "Existing solutions", icon: <Package className="size-[18px]" /> },
      { to: "/library", label: "Knowledge base", icon: <Library className="size-[18px]" /> },
    ],
  },
];

const FOOTER_NAV: NavItem[] = [
  { to: "/usage", label: "Usage", icon: <BarChart3 className="size-[18px]" /> },
  { to: "/settings", label: "Settings", icon: <Settings2 className="size-[18px]" /> },
];

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Home"],
  [/^\/proposals\/.+/, "Proposal"],
  [/^\/proposals/, "Proposals"],
  [/^\/new/, "New proposal"],
  [/^\/deals/, "Deal analysis"],
  [/^\/bid-check/, "Bid check"],
  [/^\/market/, "Market scan"],
  [/^\/solutions/, "Existing solutions"],
  [/^\/library/, "Knowledge base"],
  [/^\/usage/, "Usage"],
  [/^\/settings/, "Settings"],
];

function Logo({ withName }: { withName: boolean }) {
  return (
    <div className="flex items-center gap-2.5 px-1">
      <svg viewBox="0 0 32 32" className="size-7 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="8" fill="var(--color-raised)" />
        <path d="M10 8h8.5a5.5 5.5 0 0 1 0 11H14v5h-4z" fill="none" stroke="var(--color-ion)" strokeWidth="2.6" strokeLinejoin="round" />
        <circle cx="22.5" cy="23.5" r="2.5" fill="var(--color-ion)" />
      </svg>
      <AnimatePresence initial={false}>
        {withName && (
          <motion.span
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -4, transition: { duration: 0.1 } }}
            transition={spring.smooth}
            className="whitespace-nowrap text-body font-semibold text-ink"
          >
            Proposal Studio
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  );
}

function NavRow({ item, expanded, onNavigate }: { item: NavItem; expanded: boolean; onNavigate?: () => void }) {
  const link = (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        clsx(
          "relative flex h-9 items-center gap-3 rounded-control px-2.5 text-body outline-none transition-colors",
          isActive ? "text-ink" : "text-ink-2 hover:text-ink",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="nav-active"
              transition={spring.snappy}
              className="absolute inset-0 rounded-control bg-raised shadow-[inset_0_1px_0_rgb(255_255_255/0.09),0_0_0_1px_rgb(123_140_255/0.14)]"
            />
          )}
          <motion.span
            animate={{ scale: isActive ? 1.1 : 1 }}
            transition={spring.snappy}
            className={clsx("relative shrink-0", isActive && "text-ion")}
          >
            {item.icon}
          </motion.span>
          {expanded && <span className="relative truncate">{item.label}</span>}
        </>
      )}
    </NavLink>
  );
  if (expanded) return link;
  return (
    <Tooltip.Root delayDuration={250}>
      <Tooltip.Trigger asChild>{link}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content side="right" sideOffset={10} className="z-50 rounded-control border border-line bg-overlay px-2.5 py-1 text-small text-ink shadow-float">
          {item.label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

function Sidebar({ expanded, onToggle, onNavigate, mobile }: {
  expanded: boolean;
  onToggle?: () => void;
  onNavigate?: () => void;
  mobile?: boolean;
}) {
  return (
    <motion.aside
      animate={{ width: expanded ? 236 : 64 }}
      transition={spring.smooth}
      className={clsx(
        "flex h-full shrink-0 flex-col border-r border-line",
        // Mostly opaque with a light blur: the starfield animates underneath, and a 40 px blur
        // recomputed on every frame was the costliest thing on screen.
        "bg-panel/90 backdrop-blur-md",
        mobile && "w-[236px]",
      )}
      aria-label="Main navigation"
    >
      <div className="flex h-14 items-center px-3.5">
        <Logo withName={expanded} />
      </div>
      <nav className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-3 pt-2">
        {NAV.map((group) => (
          <div key={group.group} className="flex flex-col gap-0.5">
            {expanded ? (
              <span className="px-2.5 pb-1 text-caption text-ink-3">{group.group}</span>
            ) : (
              <span className="mx-2.5 mb-1 h-px bg-line" aria-hidden />
            )}
            {group.items.map((item) => (
              <NavRow key={item.to} item={item} expanded={expanded} onNavigate={onNavigate} />
            ))}
          </div>
        ))}
      </nav>
      <div className="flex flex-col gap-0.5 border-t border-line px-3 py-3">
        {FOOTER_NAV.map((item) => (
          <NavRow key={item.to} item={item} expanded={expanded} onNavigate={onNavigate} />
        ))}
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
            className="mt-1 flex h-8 items-center gap-3 rounded-control px-2.5 text-small text-ink-3 hover:text-ink-2"
          >
            <motion.span animate={{ rotate: expanded ? 0 : 180 }} transition={spring.snappy} className="shrink-0">
              <ChevronsLeft className="size-4" />
            </motion.span>
            {expanded && <span>Collapse</span>}
          </button>
        )}
      </div>
    </motion.aside>
  );
}

function ConnectionStatus() {
  const { state, data } = useReadiness();
  const label = {
    ready: "Models ready",
    degraded: "No Groq key",
    offline: "API offline",
    checking: "Checking",
  }[state];
  const dot = { ready: "bg-good", degraded: "bg-warn", offline: "bg-bad", checking: "bg-ink-3" }[state];
  const checks = data?.checks;
  return (
    <Popover.Root>
      <Popover.Trigger className="flex h-8 items-center gap-2 rounded-control px-2.5 text-small text-ink-2 hover:bg-wash hover:text-ink">
        <span className={clsx("size-2 rounded-full", dot, state === "ready" && "dot-pulse")} aria-hidden />
        <span className="hidden sm:inline">{label}</span>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} asChild>
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={spring.snappy}
            className="z-50 w-80 rounded-panel border border-line bg-overlay/95 p-4 text-small shadow-float backdrop-blur-xl"
          >
            <p className="font-semibold text-ink">System status</p>
            {!checks ? (
              <p className="mt-2 text-ink-3">The API did not answer. Start it with uvicorn and refresh.</p>
            ) : (
              <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
                <dt className="text-ink-3">Writer</dt>
                <dd className="text-ink">{checks.llm.frontier_model}</dd>
                <dt className="text-ink-3">Router</dt>
                <dd className="text-ink">{checks.llm.fast_model}</dd>
                <dt className="text-ink-3">Groq key</dt>
                <dd className={checks.llm.configured ? "text-ink" : "text-warn-text"}>
                  {checks.llm.configured ? "Configured" : "Missing: drafts are outlines only"}
                </dd>
                <dt className="text-ink-3">Database</dt>
                <dd className="text-ink">{checks.database.ok ? `Connected, ${checks.database.migration}` : "Unavailable"}</dd>
                <dt className="text-ink-3">Cache</dt>
                <dd className="text-ink">{checks.redis.ok ? "Redis" : "In-process (Redis offline)"}</dd>
              </dl>
            )}
          </motion.div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function ProfileSwitcher() {
  const { name, profiles, profile, setName } = useProfile();
  const [open, setOpen] = useState(false);
  const current = profiles.find((p) => p.name === name);
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger className="flex h-8 max-w-56 items-center gap-2 rounded-control border border-line px-2.5 text-small text-ink-2 hover:border-line-strong hover:text-ink">
        <span className="truncate">{current?.display_name ?? profile?.display_name ?? name}</span>
        <ChevronsUpDown className="size-3.5 shrink-0 text-ink-3" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} asChild>
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={spring.snappy}
            className="z-50 w-80 rounded-panel border border-line bg-overlay/95 p-1.5 shadow-float backdrop-blur-xl"
          >
            <p className="px-2.5 pb-1.5 pt-1 text-caption text-ink-3">Domain profile: offerings, sections, and categories the agents use</p>
            {profiles.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => {
                  setName(p.name);
                  setOpen(false);
                }}
                className="flex w-full items-start gap-2.5 rounded-control px-2.5 py-2 text-left hover:bg-wash"
              >
                <span className="mt-0.5 size-4 shrink-0 text-ion">{p.name === name && <Check className="size-4" />}</span>
                <span className="min-w-0">
                  <span className="block text-small font-semibold text-ink">{p.display_name}</span>
                  <span className="block text-caption text-ink-3">{p.description}</span>
                </span>
              </button>
            ))}
          </motion.div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatches(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return matches;
}

export function AppShell() {
  const location = useLocation();
  const outlet = useOutlet();
  const isMobile = useMediaQuery("(max-width: 767px)");
  const isNarrow = useMediaQuery("(max-width: 1180px)");
  const [expanded, setExpanded] = useState(() => {
    try {
      return localStorage.getItem("rfp.sidebar") !== "collapsed";
    } catch {
      return true;
    }
  });
  const [drawer, setDrawer] = useState(false);
  const [palette, setPalette] = useState(false);
  const mainRef = useRef<HTMLElement>(null);
  const title = TITLES.find(([re]) => re.test(location.pathname))?.[1] ?? "";

  // Each page opens at the top; the scroll container would otherwise keep the previous page's offset.
  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [location.pathname]);

  useEffect(() => {
    document.title = title ? `${title} · Proposal Studio` : "Proposal Studio";
  }, [title]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggle = () => {
    setExpanded((v) => {
      try {
        localStorage.setItem("rfp.sidebar", v ? "collapsed" : "expanded");
      } catch {
        /* ignore */
      }
      return !v;
    });
  };

  return (
    <Tooltip.Provider>
      <StarField />
      <div className="relative z-[1] flex h-dvh overflow-hidden">
        {!isMobile && <Sidebar expanded={expanded && !isNarrow} onToggle={isNarrow ? undefined : toggle} />}
        <AnimatePresence>
          {isMobile && drawer && (
            <>
              <motion.div
                className="fixed inset-0 z-40 bg-black/50"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setDrawer(false)}
              />
              <motion.div
                className="fixed inset-y-0 left-0 z-50"
                initial={{ x: -260 }}
                animate={{ x: 0 }}
                exit={{ x: -260 }}
                transition={spring.smooth}
                drag="x"
                dragConstraints={{ left: -260, right: 0 }}
                dragElastic={0.05}
                onDragEnd={(_, info) => (info.offset.x < -80 || info.velocity.x < -500) && setDrawer(false)}
              >
                <Sidebar expanded mobile onNavigate={() => setDrawer(false)} />
              </motion.div>
            </>
          )}
        </AnimatePresence>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-canvas/85 px-4 backdrop-blur-md shadow-[0_1px_12px_-4px_rgb(0_0_0/0.2)] sm:px-6">
            {isMobile && (
              <button type="button" onClick={() => setDrawer(true)} aria-label="Open navigation" className="-ml-1 rounded-control p-1.5 text-ink-2 hover:text-ink">
                <Menu className="size-5" />
              </button>
            )}
            <p className="min-w-0 truncate text-body font-semibold text-ink">{title}</p>
            <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={() => setPalette(true)}
                className="hidden h-8 w-60 items-center gap-2 rounded-control border border-line bg-panel px-2.5 text-small text-ink-3 hover:border-line-strong md:flex"
              >
                <Search className="size-3.5" />
                <span>Search or jump to</span>
                <span className="ml-auto"><Kbd>⌘K</Kbd></span>
              </button>
              <button type="button" onClick={() => setPalette(true)} aria-label="Search" className="rounded-control p-1.5 text-ink-2 md:hidden">
                <Search className="size-4" />
              </button>
              <ProfileSwitcher />
              <ThemeToggle />
              <AccountButton />
              <ConnectionStatus />
            </div>
          </header>
          <main ref={mainRef} className="relative min-h-0 flex-1 overflow-y-auto">
            <motion.div
              key={location.pathname.split("/").slice(0, 3).join("/")}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              className="min-h-full"
            >
              {outlet}
            </motion.div>
          </main>
        </div>
      </div>
      <CommandPalette open={palette} onOpenChange={setPalette} />
    </Tooltip.Provider>
  );
}


/** Shows who is signed in and offers sign-out; renders nothing when the server has no accounts in play. */
function AccountButton() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  const initial = (user.name || user.email).charAt(0).toUpperCase();
  return (
    <button
      type="button"
      title={`Sign out ${user.email}`}
      aria-label={`Sign out ${user.email}`}
      onClick={async () => {
        await signOut();
        navigate("/login", { replace: true });
      }}
      className="group flex h-8 items-center gap-1.5 rounded-full border border-line bg-panel pl-1 pr-2.5 text-small text-ink-2 hover:border-line-strong hover:text-ink"
    >
      <span className="grid size-6 place-items-center rounded-full bg-ion-soft text-caption font-semibold text-ion-strong">{initial}</span>
      <LogOut className="size-3.5" aria-hidden />
    </button>
  );
}
