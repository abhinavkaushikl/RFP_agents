import clsx from "clsx";
import { FileUp } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState, type ReactNode } from "react";

import { spring } from "@/lib/motion";

export const DOCUMENT_TYPES = ".pdf,.docx,.md,.markdown,.txt,.eml";

/** Drop files here or click to browse. The zone leans toward the cursor's file with a spring. */
export function DropZone({ onFiles, multiple, accept = DOCUMENT_TYPES, title, hint, busy, compact, children }: {
  onFiles: (files: File[]) => void;
  multiple?: boolean;
  accept?: string;
  title: string;
  hint?: string;
  busy?: boolean;
  compact?: boolean;
  children?: ReactNode;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const take = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (files.length) onFiles(multiple ? files : files.slice(0, 1));
  };

  return (
    <motion.div
      role="button"
      tabIndex={0}
      aria-label={title}
      aria-busy={busy}
      onClick={() => input.current?.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), input.current?.click())}
      onDragEnter={(e) => (e.preventDefault(), setOver(true))}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={(e) => e.currentTarget.contains(e.relatedTarget as Node) || setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        take(e.dataTransfer.files);
      }}
      animate={{ scale: over ? 1.012 : 1 }}
      whileTap={{ scale: 0.995 }}
      transition={spring.snappy}
      className={clsx(
        "group relative flex cursor-pointer flex-col items-center justify-center rounded-panel border border-dashed text-center outline-none transition-colors",
        compact ? "gap-2 px-4 py-6" : "gap-3 px-6 py-12",
        over ? "border-ion bg-ion-soft" : "border-line-strong bg-panel/60 hover:border-ink-3/60",
      )}
    >
      <motion.div
        animate={{ y: over ? -4 : 0 }}
        transition={spring.land}
        className={clsx("flex size-10 items-center justify-center rounded-full", over ? "bg-ion text-on-ion" : "bg-raised text-ink-2")}
      >
        <FileUp className="size-5" aria-hidden />
      </motion.div>
      <div>
        <p className="text-body font-semibold text-ink">{busy ? "Reading…" : title}</p>
        {hint && <p className="mt-0.5 text-small text-ink-3">{hint}</p>}
      </div>
      {children}
      <input
        ref={input}
        type="file"
        className="sr-only"
        accept={accept}
        multiple={multiple}
        tabIndex={-1}
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
    </motion.div>
  );
}
