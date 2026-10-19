import clsx from "clsx";
import { Monitor, Moon, Sun } from "lucide-react";
import { motion } from "motion/react";

import { useTheme, type ThemePreference } from "@/hooks/useTheme";
import { spring } from "@/lib/motion";

const OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Match system", icon: Monitor },
];

/** Compact light / dark / system switch with a sliding thumb. */
export function ThemeToggle() {
  const { preference, setPreference } = useTheme();
  return (
    <div role="radiogroup" aria-label="Appearance" className="hidden h-8 items-center rounded-control border border-line bg-seg-track p-0.5 sm:inline-flex">
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = preference === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={(e) => {
              const box = e.currentTarget.getBoundingClientRect();
              setPreference(value, { x: box.left + box.width / 2, y: box.top + box.height / 2 });
            }}
            className={clsx("relative flex h-full w-7 items-center justify-center rounded-[6px] transition-colors", active ? "text-ink" : "text-ink-3 hover:text-ink-2")}
          >
            {active && <motion.span layoutId="theme-thumb" transition={spring.snappy} className="absolute inset-0 rounded-[6px] bg-seg-thumb shadow-lift" />}
            <Icon className="relative size-3.5" aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
