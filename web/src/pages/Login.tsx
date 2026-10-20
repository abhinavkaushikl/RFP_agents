import { ArrowRight, Check, Eye, EyeOff, Loader2, ShieldCheck, Sparkles, TrendingUp } from "lucide-react";
import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring, useTransform } from "motion/react";
import { useRef, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

import { spring } from "@/lib/motion";

const EASE = [0.65, 0, 0.35, 1] as const;
const LOOP = 6; // seconds for one full handshake cycle

/** Two hands glide in, clasp, shake once, and a "deal done" ring blooms. Loops forever. */
function Handshake() {
  const reduce = useReducedMotion();
  const times = [0, 0.28, 0.4, 0.46, 0.52, 0.58, 0.85, 1];
  const loop = { duration: LOOP, times, ease: EASE, repeat: Infinity } as const;

  return (
    <svg viewBox="0 0 520 380" className="w-full max-w-[560px] overflow-visible" role="img" aria-label="Two people shaking hands to close a deal">
      <defs>
        <linearGradient id="sleeveL" x1="0" x2="1">
          <stop offset="0" stopColor="#4b57d6" />
          <stop offset="1" stopColor="#7b8cff" />
        </linearGradient>
        <linearGradient id="sleeveR" x1="1" x2="0">
          <stop offset="0" stopColor="#1f2430" />
          <stop offset="1" stopColor="#3a4152" />
        </linearGradient>
        <linearGradient id="skinL" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f3c9a5" />
          <stop offset="1" stopColor="#e2a982" />
        </linearGradient>
        <linearGradient id="skinR" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#b9805a" />
          <stop offset="1" stopColor="#9a6544" />
        </linearGradient>
        <radialGradient id="halo">
          <stop offset="0" stopColor="#9aa7ff" stopOpacity="0.55" />
          <stop offset="1" stopColor="#9aa7ff" stopOpacity="0" />
        </radialGradient>
        <filter id="soft" x="-20%" y="-20%" width="140%" height="160%">
          <feDropShadow dx="0" dy="14" stdDeviation="14" floodColor="#000" floodOpacity="0.35" />
        </filter>
      </defs>

      {/* halo + ripple rings that bloom on contact */}
      <motion.circle cx="260" cy="196" r="150" fill="url(#halo)" animate={reduce ? undefined : { opacity: [0.25, 0.25, 1, 0.5, 0.25], scale: [0.9, 0.9, 1.1, 1, 0.9] }} transition={{ duration: LOOP, repeat: Infinity, ease: "easeInOut", times: [0, 0.3, 0.45, 0.7, 1] }} style={{ transformOrigin: "260px 196px" }} />
      {[0, 0.18].map((d) => (
        <motion.circle
          key={d}
          cx="260"
          cy="196"
          r="40"
          fill="none"
          stroke="#9aa7ff"
          strokeWidth="1.5"
          initial={{ opacity: 0 }}
          animate={reduce ? undefined : { opacity: [0, 0, 0.7, 0, 0], scale: [0.5, 0.5, 0.5, 3.4, 3.4] }}
          transition={{ duration: LOOP, repeat: Infinity, ease: "easeOut", times: [0, 0.4, 0.42, 0.75, 1], delay: d }}
          style={{ transformOrigin: "260px 196px" }}
        />
      ))}

      {/* the joined clasp shakes as one body */}
      <motion.g
        filter="url(#soft)"
        style={{ transformOrigin: "260px 196px" }}
        animate={reduce ? undefined : { rotate: [0, 0, 0, -4, 4, -3, 0, 0], y: [0, 0, 0, 4, -4, 3, 0, 0] }}
        transition={loop}
      >
        {/* left person */}
        <motion.g animate={reduce ? undefined : { x: [-190, -190, 0, 0, 0, 0, -190, -190], opacity: [0, 1, 1, 1, 1, 1, 1, 0] }} initial={reduce ? { x: 0 } : undefined} transition={loop}>
          <rect x="-40" y="162" width="190" height="74" rx="22" fill="url(#sleeveL)" />
          <rect x="138" y="156" width="26" height="86" rx="9" fill="#f4f5fa" />
          <path d="M164 168 H262 C292 168 318 178 336 194 C346 203 340 218 326 218 H300 C292 218 288 222 280 226 C270 234 258 236 246 236 H164 Z" fill="url(#skinL)" />
        </motion.g>

        {/* right person */}
        <motion.g animate={reduce ? undefined : { x: [190, 190, 0, 0, 0, 0, 190, 190], opacity: [0, 1, 1, 1, 1, 1, 1, 0] }} initial={reduce ? { x: 0 } : undefined} transition={loop}>
          <rect x="370" y="170" width="190" height="74" rx="22" fill="url(#sleeveR)" />
          <rect x="356" y="164" width="26" height="86" rx="9" fill="#e7e9f0" />
          <path d="M356 176 H268 C246 176 226 184 212 196 C204 204 208 216 220 216 H236 C244 216 250 224 258 230 C270 242 284 244 296 244 H356 Z" fill="url(#skinR)" />
          {/* fingers wrapping over the other hand */}
          {[0, 1, 2, 3].map((i) => (
            <rect key={i} x={226 + i * 14} y={190 + i * 1.5} width="11" height="38" rx="5.5" fill="url(#skinR)" stroke="#7d4f33" strokeOpacity="0.35" strokeWidth="1" transform={`rotate(-12 ${232 + i * 14} 210)`} />
          ))}
        </motion.g>
        {/* thumb of the left hand crossing the top */}
        <motion.path d="M296 170 C310 160 330 162 340 174 C346 182 338 190 330 188 L300 182 Z" fill="url(#skinL)" animate={reduce ? undefined : { opacity: [0, 0, 1, 1, 1, 1, 0, 0] }} initial={reduce ? { opacity: 1 } : undefined} transition={loop} />
      </motion.g>

      {/* deal-closed badge pops after the shake */}
      <motion.g
        style={{ transformOrigin: "260px 96px" }}
        initial={{ opacity: 0 }}
        animate={reduce ? { opacity: 1 } : { opacity: [0, 0, 0, 1, 1, 1, 0, 0], scale: [0.7, 0.7, 0.7, 1.08, 1, 1, 0.9, 0.9], y: [10, 10, 10, 0, 0, 0, -6, -6] }}
        transition={{ duration: LOOP, times: [0, 0.4, 0.5, 0.6, 0.66, 0.85, 0.95, 1], repeat: Infinity, ease: "easeOut" }}
      >
        <rect x="190" y="70" width="140" height="40" rx="20" fill="rgba(255,255,255,0.1)" stroke="rgba(255,255,255,0.22)" />
        <circle cx="214" cy="90" r="9" fill="#2fbf71" />
        <path d="M209.5 90.2l3.2 3.2 5.6-6" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <text x="232" y="95" fill="#eceef3" fontSize="14" fontWeight="600" fontFamily="inherit">Deal closed</text>
      </motion.g>
    </svg>
  );
}

const AppleIcon = () => (
  <svg viewBox="0 0 24 24" className="size-4" fill="currentColor" aria-hidden>
    <path d="M16.4 12.7c0-2.4 2-3.5 2.1-3.6-1.1-1.7-2.9-1.9-3.5-1.9-1.5-.2-2.9.9-3.7.9-.8 0-1.9-.9-3.2-.8-1.6 0-3.1 1-4 2.4-1.7 3-.4 7.400 1.200 9.800.8 1.200 1.800 2.500 3 2.500 1.200 0 1.700-.8 3.100-.8 1.500 0 1.900.8 3.200.7 1.300 0 2.100-1.200 2.900-2.400.9-1.400 1.300-2.700 1.300-2.800-.1 0-2.400-.9-2.400-3.800zM14 5.600c.7-.8 1.100-1.900 1-3-1 0-2.100.7-2.800 1.500-.6.700-1.200 1.800-1 2.900 1.100.1 2.200-.6 2.800-1.400z" />
  </svg>
);
const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" className="size-4" aria-hidden>
    <path fill="#4285F4" d="M22 12.2c0-.7-.1-1.400-.2-2H12v3.900h5.600a4.800 4.800 0 0 1-2.100 3.100v2.600h3.400c2-1.800 3.100-4.500 3.100-7.600z" />
    <path fill="#34A853" d="M12 22.500c2.800 0 5.200-.9 6.900-2.500l-3.400-2.600c-.9.600-2.100 1-3.500 1-2.700 0-5-1.800-5.800-4.300H2.700v2.700A10.500 10.500 0 0 0 12 22.500z" />
    <path fill="#FBBC05" d="M6.200 14.100a6.300 6.300 0 0 1 0-4.200V7.200H2.700a10.500 10.500 0 0 0 0 9.600l3.500-2.700z" />
    <path fill="#EA4335" d="M12 5.600c1.500 0 2.900.5 4 1.600l3-3A10.500 10.500 0 0 0 2.700 7.200l3.500 2.700C7 7.400 9.300 5.600 12 5.600z" />
  </svg>
);

/** A mini proposal that "writes itself" in step with the handshake loop. */
function ProposalCard() {
  const reduce = useReducedMotion();
  const widths = ["86%", "64%", "78%", "48%"];
  return (
    <div className="w-[236px] rounded-[18px] border border-white/12 bg-white/[0.07] p-4 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.6),inset_0_1px_0_rgb(255_255_255/0.12)] backdrop-blur-md">
      <div className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-[10px] bg-gradient-to-br from-[#7b8cff] to-[#c06bff]"><Sparkles className="size-4 text-white" /></span>
        <div className="leading-tight">
          <p className="text-small font-semibold text-white">Acme Corp · RFP #2048</p>
          <p className="text-caption text-white/50">Drafting response…</p>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        {widths.map((w, i) => (
          <motion.div key={i} className="h-2 rounded-full bg-white/15" initial={{ width: "20%" }} animate={reduce ? { width: w } : { width: ["0%", w, w, "0%"] }} transition={{ duration: LOOP, repeat: Infinity, ease: EASE, times: [0, 0.35 + i * 0.05, 0.9, 1] }} />
        ))}
      </div>
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
        <motion.div className="h-full rounded-full bg-gradient-to-r from-[#7b8cff] to-[#2fbf71]" animate={reduce ? { width: "100%" } : { width: ["0%", "100%", "100%", "0%"] }} transition={{ duration: LOOP, repeat: Infinity, ease: EASE, times: [0, 0.5, 0.9, 1] }} />
      </div>
    </div>
  );
}

function StatCard() {
  return (
    <div className="flex w-[196px] items-center gap-3 rounded-[18px] border border-white/12 bg-white/[0.07] p-3.5 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.6),inset_0_1px_0_rgb(255_255_255/0.12)] backdrop-blur-md">
      <span className="grid size-10 place-items-center rounded-[12px] bg-[#2fbf71]/20 text-[#5be39a]"><TrendingUp className="size-5" /></span>
      <div className="leading-tight">
        <p className="text-title font-semibold tracking-tight text-white">3.2× faster</p>
        <p className="text-caption text-white/50">than manual drafting</p>
      </div>
    </div>
  );
}

function Backdrop() {
  const reduce = useReducedMotion();
  // Soft blobs are radial gradients, not blurred circles: a blur filter on a moving layer is re-run every frame.
  const blob = (cls: string, color: string, x: number[], y: number[], dur: number) => (
    <motion.div
      aria-hidden
      className={`absolute rounded-full ${cls}`}
      style={{ background: `radial-gradient(closest-side, ${color} 35%, transparent)` }}
      animate={reduce ? undefined : { x, y }}
      transition={{ duration: dur, repeat: Infinity, repeatType: "mirror", ease: "easeInOut" }}
    />
  );
  return (
    <div className="absolute inset-0 overflow-hidden">
      {blob("-left-32 -top-8 size-[560px]", "rgb(91 107 255 / 0.45)", [0, 80, -20], [0, 60, 20], 14)}
      {blob("-right-12 top-1/4 size-[500px]", "rgb(192 107 255 / 0.32)", [0, -90, 20], [0, -40, 50], 17)}
      {blob("-bottom-12 left-1/4 size-[460px]", "rgb(47 181 255 / 0.3)", [0, 60, -40], [0, -60, 0], 19)}
      <div aria-hidden className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "radial-gradient(#fff 1px, transparent 1px)", backgroundSize: "26px 26px", maskImage: "radial-gradient(ellipse at center, #000 30%, transparent 75%)" }} />
      {/* film grain keeps the gradients from banding */}
      <div aria-hidden className="absolute inset-0 opacity-[0.06] mix-blend-overlay" style={{ backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")" }} />
    </div>
  );
}

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const celebrating = useRef(false);
  const { ready, user, signupEnabled, signIn, signUp } = useAuth();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const reduce = useReducedMotion();
  const mx = useMotionValue(0.5);
  const my = useMotionValue(0.5);
  const sx = useSpring(mx, { stiffness: 80, damping: 20 });
  const sy = useSpring(my, { stiffness: 80, damping: 20 });
  const rotY = useTransform(sx, [0, 1], [-7, 7]);
  const rotX = useTransform(sy, [0, 1], [5, -5]);
  const spot = useMotionTemplate`radial-gradient(520px circle at ${useTransform(sx, [0, 1], ["0%", "100%"])} ${useTransform(sy, [0, 1], ["0%", "100%"])}, rgb(154 167 255 / 0.16), transparent 60%)`;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    celebrating.current = true;
    try {
      if (mode === "signup") await signUp(name.trim(), email.trim(), password);
      else await signIn(email.trim(), password);
      setDone(true);
      setTimeout(() => navigate(from, { replace: true }), 550);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
      celebrating.current = false;
      setBusy(false);
    }
  }

  const field =
    "peer h-12 w-full rounded-[12px] border border-line-strong bg-fill px-4 pt-4 text-body text-ink outline-none transition placeholder-transparent focus:border-ion focus:bg-wash focus:shadow-[0_0_0_4px_var(--color-ion-soft)]";
  const label =
    "pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-body text-ink-3 transition-all peer-focus:top-3.5 peer-focus:text-caption peer-focus:text-ion-strong peer-[:not(:placeholder-shown)]:top-3.5 peer-[:not(:placeholder-shown)]:text-caption";

  if (ready && user && !celebrating.current) return <Navigate to={from} replace />;

  return (
    <main className="grid min-h-dvh bg-canvas text-ink lg:grid-cols-[minmax(420px,5fr)_7fr]">
      <section className="relative z-10 flex flex-col justify-between overflow-hidden px-6 py-8 sm:px-14">
        <div aria-hidden className="pointer-events-none absolute -left-40 -top-40 size-[540px] rounded-full" style={{ background: "radial-gradient(closest-side, rgb(91 107 255 / 0.2) 35%, transparent)" }} />
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={spring.smooth} className="flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-[9px] bg-gradient-to-br from-[#7b8cff] to-[#4b57d6] shadow-[0_6px_18px_-4px_var(--color-glow-strong)]">
            <svg viewBox="0 0 24 24" className="size-4.5" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M6 4h8l4 4v12H6z" />
              <path d="M9 13h6M9 17h4" />
            </svg>
          </span>
          <span className="text-lead font-semibold tracking-tight">Proposal Builder</span>
        </motion.div>

        <div className="relative mx-auto w-full max-w-[420px] py-10">
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-ion-line bg-ion-soft px-3 py-1 text-caption font-medium text-ion-strong"><Sparkles className="size-3" /> AI-powered proposals</motion.span>
          <motion.h1 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring.smooth, delay: 0.05 }} className="text-[3.1rem] font-semibold leading-[1.02] tracking-[-0.04em]">
            RFP in <span className="bg-gradient-to-r from-[#9aa7ff] to-[#d29bff] bg-clip-text text-transparent">minutes.</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring.smooth, delay: 0.12 }} className="mt-3 text-lead text-ink-2">
            Sign in and turn any request for proposal into a winning response.
          </motion.p>

          <motion.form onSubmit={submit} initial="hide" animate="show" variants={{ show: { transition: { staggerChildren: 0.07, delayChildren: 0.2 } } }} className="mt-8 space-y-3.5 rounded-[24px] border border-white/10 bg-white/[0.035] p-6 shadow-[0_30px_80px_-30px_rgb(0_0_0/0.7),inset_0_1px_0_rgb(255_255_255/0.08)] backdrop-blur-xl">
            {[
              ...(mode === "signup"
                ? [
                    <div key="n" className="relative">
                      <input id="name" type="text" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className={field} />
                      <label htmlFor="name" className={label}>Name (optional)</label>
                    </div>,
                  ]
                : []),
              <div key="e" className="relative">
                <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className={field} />
                <label htmlFor="email" className={label}>Email</label>
              </div>,
              <div key="p" className="relative">
                <input id="password" type={show ? "text" : "password"} autoComplete={mode === "signup" ? "new-password" : "current-password"} required minLength={mode === "signup" ? 8 : undefined} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" className={`${field} pr-12`} />
                <label htmlFor="password" className={label}>Password</label>
                <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-3 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-full text-ink-3 transition hover:bg-wash hover:text-ink">
                  {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>,
              ...(error ? [<p key="err" role="alert" className="rounded-[10px] border border-bad/30 bg-bad/10 px-3 py-2 text-small text-bad-text">{error}</p>] : []),
              <div key="b">
                <motion.button
                  type="submit"
                  whileHover={{ scale: 1.015 }}
                  whileTap={{ scale: 0.97 }}
                  transition={spring.snappy}
                  className="group relative flex h-12 w-full items-center justify-center gap-2 overflow-hidden rounded-[12px] bg-gradient-to-b from-[#8c9bff] to-[#6577f5] text-body font-semibold text-on-ion shadow-[0_10px_28px_-8px_var(--color-glow-strong),inset_0_1px_0_rgb(255_255_255/0.35)]"
                >
                  <span aria-hidden className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
                  {done ? <><Check className="size-4.5" /> {mode === "signup" ? "Account created" : "Welcome back"}</> : busy ? <Loader2 className="size-4.5 animate-spin" /> : <>{mode === "signup" ? "Create account" : "Continue"} <ArrowRight className="size-4.5 transition-transform group-hover:translate-x-0.5" /></>}
                </motion.button>
              </div>,
              <div key="o" className="flex items-center gap-3 py-1 text-caption text-ink-3">
                <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
              </div>,
              <div key="s" className="grid grid-cols-2 gap-3">
                {[["Apple", <AppleIcon key="a" />], ["Google", <GoogleIcon key="g" />]].map(([p, icon]) => (
                  <motion.button key={p as string} type="button" whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }} transition={spring.snappy} className="flex h-11 items-center justify-center gap-2 rounded-[12px] border border-line-strong bg-fill text-small font-medium text-ink-2 transition hover:bg-wash hover:text-ink">
                    {icon}
                    {p}
                  </motion.button>
                ))}
              </div>,
            ].map((child) => (
              <motion.div key={child.key} variants={{ hide: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: spring.smooth } }}>
                {child}
              </motion.div>
            ))}
          </motion.form>
        </div>

        <p className="flex items-center gap-1.5 text-caption text-ink-3">
          <ShieldCheck className="size-3.5" />
          {mode === "signin" ? (
            signupEnabled ? (
              <>New here? <button type="button" onClick={() => { setMode("signup"); setError(null); }} className="text-ion-strong hover:underline">Create an account</button></>
            ) : (
              <span>Accounts are created by your administrator.</span>
            )
          ) : (
            <>Already have an account? <button type="button" onClick={() => { setMode("signin"); setError(null); }} className="text-ion-strong hover:underline">Sign in</button></>
          )}
        </p>
      </section>

      <section
        className="relative hidden overflow-hidden border-l border-line bg-[#0c0e14] lg:grid lg:place-items-center"
        onMouseMove={(e) => {
          if (reduce) return;
          const r = e.currentTarget.getBoundingClientRect();
          mx.set((e.clientX - r.left) / r.width);
          my.set((e.clientY - r.top) / r.height);
        }}
      >
        <Backdrop />
        <motion.div aria-hidden className="absolute inset-0" style={{ background: spot }} />
        <div className="relative w-full px-10" style={{ perspective: 1200 }}>
          <motion.div className="relative mx-auto grid max-w-[640px] place-items-center" style={reduce ? undefined : { rotateX: rotX, rotateY: rotY, transformStyle: "preserve-3d" }}>
            <Handshake />
            <motion.div className="absolute -left-4 top-[2%]" style={{ translateZ: 70 }} animate={reduce ? undefined : { y: [0, -9, 0] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}>
              <ProposalCard />
            </motion.div>
            <motion.div className="absolute -right-2 bottom-[4%]" style={{ translateZ: 90 }} animate={reduce ? undefined : { y: [0, 9, 0] }} transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}>
              <StatCard />
            </motion.div>
          </motion.div>
          <p className="mt-10 text-center text-lead text-white/60">From requirements to a signed deal, <span className="text-white/90">in one fluid motion.</span></p>
        </div>
      </section>
    </main>
  );
}
