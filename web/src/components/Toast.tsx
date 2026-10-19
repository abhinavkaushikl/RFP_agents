import { CheckCircle2, Info, XCircle } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

import { spring } from "@/lib/motion";

type ToastTone = "good" | "bad" | "info";
interface ToastItem { id: number; tone: ToastTone; title: string; detail?: string }

const ToastContext = createContext<(t: Omit<ToastItem, "id">) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((t: Omit<ToastItem, "id">) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev.slice(-3), { ...t, id }]);
    setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), t.tone === "bad" ? 7000 : 4000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
        <AnimatePresence initial={false}>
          {items.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 24, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 60, transition: { duration: 0.16 } }}
              transition={spring.land}
              drag="x"
              dragConstraints={{ left: 0, right: 0 }}
              dragElastic={{ left: 0.1, right: 0.8 }}
              onDragEnd={(_, info) => info.offset.x > 80 && setItems((prev) => prev.filter((x) => x.id !== t.id))}
              className="pointer-events-auto flex gap-3 rounded-panel border border-line bg-overlay/95 px-4 py-3 shadow-float backdrop-blur-xl"
            >
              {t.tone === "good" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-good" /> : t.tone === "bad" ? <XCircle className="mt-0.5 size-4 shrink-0 text-bad" /> : <Info className="mt-0.5 size-4 shrink-0 text-ion" />}
              <div className="min-w-0 text-small">
                <p className="font-semibold text-ink">{t.title}</p>
                {t.detail && <p className="mt-0.5 text-ink-2">{t.detail}</p>}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
