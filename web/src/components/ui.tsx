import clsx from "clsx";
import { AlertTriangle, CheckCircle2, ChevronDown, CircleDashed, Info, Loader2, XCircle } from "lucide-react";
import { motion, type HTMLMotionProps } from "motion/react";
import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import { spring } from "@/lib/motion";

/* ── Button ─────────────────────────────────────────────────────────── */

type Variant = "primary" | "secondary" | "ghost" | "quiet";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-ion text-on-ion font-semibold hover:bg-ion-strong disabled:bg-ion/40",
  secondary: "bg-raised text-ink border border-line-strong hover:bg-overlay",
  ghost: "text-ink-2 hover:text-ink hover:bg-wash",
  quiet: "text-ion-strong hover:bg-ion-soft",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-small gap-1.5",
  md: "h-9 px-3.5 text-body gap-2",
  lg: "h-11 px-5 text-lead gap-2",
};

export interface ButtonProps extends Omit<HTMLMotionProps<"button">, "children"> {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  loading?: boolean;
  children?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", icon, loading, className, children, disabled, ...rest },
  ref,
) {
  return (
    <motion.button
      ref={ref}
      whileTap={disabled || loading ? undefined : { scale: 0.97 }}
      transition={spring.snappy}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex select-none items-center justify-center rounded-control whitespace-nowrap transition-colors duration-150",
        "disabled:cursor-not-allowed disabled:opacity-60",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </motion.button>
  );
});

export function IconButton({ label, className, children, ...rest }: ButtonProps & { label: string }) {
  return (
    <Button variant="ghost" size="sm" aria-label={label} title={label} className={clsx("w-8 px-0", className)} {...rest}>
      {children}
    </Button>
  );
}

/* ── Form fields ────────────────────────────────────────────────────── */

const control =
  "w-full rounded-control border border-line-strong bg-panel text-ink placeholder:text-ink-3 " +
  "transition-[border-color,box-shadow] duration-150 outline-none " +
  "focus:border-ion focus:shadow-[0_0_0_3px_var(--color-ion-soft)] disabled:opacity-60";

export function Field({ label, hint, error, children, htmlFor }: {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-small font-semibold text-ink-2">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-small text-bad-text">{error}</p>
      ) : hint ? (
        <p className="text-caption text-ink-3">{hint}</p>
      ) : null}
    </div>
  );
}

export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function TextInput(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={clsx(control, "h-9 px-3", className)} {...rest} />;
});

export const TextArea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function TextArea(
  { className, ...rest },
  ref,
) {
  return <textarea ref={ref} className={clsx(control, "min-h-24 resize-y px-3 py-2.5 leading-relaxed", className)} {...rest} />;
});

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={clsx("relative", className)}>
      <select className={clsx(control, "h-9 appearance-none pl-3 pr-9")} {...rest}>
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
    </div>
  );
}

/* ── Switch ─────────────────────────────────────────────────────────── */

export function Switch({ checked, onChange, label, description }: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description?: string;
}) {
  const id = useId();
  return (
    <div className="flex items-start gap-3">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={clsx(
          "relative mt-0.5 flex h-5 w-[34px] shrink-0 items-center rounded-full p-0.5 transition-colors duration-200",
          checked ? "justify-end bg-ion" : "justify-start bg-track-off",
        )}
      >
        <motion.span layout transition={spring.snappy} className="size-4 rounded-full bg-white shadow-sm" />
      </button>
      <label htmlFor={id} className="cursor-pointer">
        <span className="block text-body text-ink">{label}</span>
        {description && <span className="block text-small text-ink-3">{description}</span>}
      </label>
    </div>
  );
}

/* ── Segmented control ──────────────────────────────────────────────── */

export function Segmented<T extends string | number>({ options, value, onChange, label }: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  const id = useId();
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-control border border-line bg-seg-track p-0.5">
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={clsx(
              "relative h-7 rounded-[6px] px-3 text-small transition-colors",
              active ? "text-ink" : "text-ink-3 hover:text-ink-2",
            )}
          >
            {active && (
              <motion.span
                layoutId={`seg-${id}`}
                transition={spring.snappy}
                className="absolute inset-0 rounded-[6px] bg-seg-thumb shadow-lift"
              />
            )}
            <span className="relative">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Status tag (icon + label, never color alone) ───────────────────── */

export type Tone = "good" | "warn" | "bad" | "neutral" | "ion" | "busy";

const toneIcon: Record<Tone, ReactNode> = {
  good: <CheckCircle2 className="size-3.5 text-good" aria-hidden />,
  warn: <AlertTriangle className="size-3.5 text-warn" aria-hidden />,
  bad: <XCircle className="size-3.5 text-bad" aria-hidden />,
  neutral: <CircleDashed className="size-3.5 text-ink-3" aria-hidden />,
  ion: <Info className="size-3.5 text-ion" aria-hidden />,
  busy: <Loader2 className="size-3.5 animate-spin text-ion" aria-hidden />,
};

export function StatusTag({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-full border border-line bg-fill px-2 py-0.5 text-caption text-ink-2", className)}>
      {toneIcon[tone]}
      {children}
    </span>
  );
}

export function Chip({ children, active, onClick }: { children: ReactNode; active?: boolean; onClick?: () => void }) {
  return (
    <motion.button
      type="button"
      layout
      whileTap={{ scale: 0.95 }}
      transition={spring.snappy}
      onClick={onClick}
      aria-pressed={active}
      className={clsx(
        "inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-small transition-colors",
        active ? "border-ion-line bg-ion-soft text-ink" : "border-line-strong text-ink-2 hover:border-ink-3/60 hover:text-ink",
      )}
    >
      {children}
    </motion.button>
  );
}

/* ── Layout helpers ─────────────────────────────────────────────────── */

export function Panel({ children, className, as: Tag = "section" }: { children: ReactNode; className?: string; as?: "section" | "div" | "aside" }) {
  return <Tag className={clsx("rounded-panel border border-line bg-panel", className)}>{children}</Tag>;
}

export function PanelHeader({ title, action, description }: { title: ReactNode; action?: ReactNode; description?: ReactNode }) {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-3.5">
      <div className="min-w-0">
        <h2 className="text-body font-semibold text-ink">{title}</h2>
        {description && <p className="mt-0.5 text-small text-ink-3">{description}</p>}
      </div>
      {action}
    </header>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-[68ch]">
        <h1 className="text-display font-semibold text-ink">{title}</h1>
        {description && <p className="mt-1.5 text-lead text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded-[5px] border border-line-strong bg-fill px-1.5 text-caption text-ink-3">{children}</kbd>;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("shimmer rounded-[6px]", className)} aria-hidden />;
}

export function EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 px-6 py-10">
      <div className="flex size-10 items-center justify-center rounded-panel bg-raised text-ink-2">{icon}</div>
      <div>
        <p className="text-body font-semibold text-ink">{title}</p>
        <p className="mt-1 max-w-[52ch] text-small text-ink-3">{description}</p>
      </div>
      {action}
    </div>
  );
}

export function Notice({ tone = "warn", title, children }: { tone?: "warn" | "bad" | "ion"; title: string; children?: ReactNode }) {
  const color = tone === "bad" ? "border-bad/40 bg-bad/[0.08]" : tone === "ion" ? "border-ion-line bg-ion-soft" : "border-warn/35 bg-warn/[0.07]";
  const icon = tone === "bad" ? <XCircle className="mt-0.5 size-4 shrink-0 text-bad" /> : tone === "ion" ? <Info className="mt-0.5 size-4 shrink-0 text-ion" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />;
  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={spring.smooth}
      role={tone === "bad" ? "alert" : "status"}
      className={clsx("flex gap-3 rounded-panel border px-4 py-3", color)}
    >
      {icon}
      <div className="min-w-0 text-small">
        <p className="font-semibold text-ink">{title}</p>
        {children && <div className="mt-0.5 text-ink-2">{children}</div>}
      </div>
    </motion.div>
  );
}
