import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";

export type ThemePreference = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

const STORAGE = "rfp.theme";
const META_COLOR: Record<ResolvedTheme, string> = { dark: "#15171c", light: "#f4f5f8" };
const lightQuery = () => window.matchMedia("(prefers-color-scheme: light)");

function readPreference(): ThemePreference {
  try {
    const v = localStorage.getItem(STORAGE);
    return v === "light" || v === "system" || v === "dark" ? v : "dark";
  } catch {
    return "dark";
  }
}

function resolve(pref: ThemePreference): ResolvedTheme {
  if (pref === "system") return lightQuery().matches ? "light" : "dark";
  return pref;
}

function apply(theme: ResolvedTheme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", META_COLOR[theme]);
}

interface ThemeContextValue {
  preference: ThemePreference;
  theme: ResolvedTheme;
  /** `origin` is where the change was triggered; the new theme grows out of that point. */
  setPreference: (pref: ThemePreference, origin?: { x: number; y: number }) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPref] = useState<ThemePreference>(readPreference);
  const [theme, setTheme] = useState<ResolvedTheme>(() => resolve(readPreference()));

  useEffect(() => apply(theme), [theme]);

  useEffect(() => {
    if (preference !== "system") return;
    const mq = lightQuery();
    const onChange = () => setTheme(mq.matches ? "light" : "dark");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [preference]);

  const setPreference = useCallback((pref: ThemePreference, origin?: { x: number; y: number }) => {
    try {
      localStorage.setItem(STORAGE, pref);
    } catch {
      /* storage unavailable: the choice lasts for this page */
    }
    const next = resolve(pref);
    const commit = () => {
      flushSync(() => {
        setPref(pref);
        setTheme(next);
      });
      apply(next);
    };
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
    if (next === resolve(preference) || reduced || !doc.startViewTransition) {
      commit();
      return;
    }
    const x = origin?.x ?? window.innerWidth;
    const y = origin?.y ?? 0;
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    const root = document.documentElement.style;
    root.setProperty("--vt-x", `${x}px`);
    root.setProperty("--vt-y", `${y}px`);
    root.setProperty("--vt-r", `${radius}px`);
    doc.startViewTransition(commit);
  }, [preference]);

  const value = useMemo(() => ({ preference, theme, setPreference }), [preference, theme, setPreference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
