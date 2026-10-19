import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { AnimatePresence, motion, useDragControls } from "motion/react";
import type { ReactNode } from "react";

import { spring } from "@/lib/motion";
import { IconButton } from "./ui";

/**
 * Side sheet. Slides in on a spring; drag it right (or flick it) to dismiss.
 * Velocity matters: a fast flick closes it even when it has only moved a little.
 */
export function Sheet({ open, onOpenChange, title, description, children, footer }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const drag = useDragControls();
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-40 bg-black/45 backdrop-blur-[2px]"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
              />
            </Dialog.Overlay>
            <Dialog.Content asChild forceMount {...(description ? {} : { "aria-describedby": undefined })}>
              <motion.div
                className="fixed inset-y-2 right-2 z-50 flex w-[min(520px,calc(100vw-1rem))] flex-col rounded-sheet border border-line bg-panel/95 shadow-float backdrop-blur-xl"
                initial={{ x: "105%" }}
                animate={{ x: 0 }}
                exit={{ x: "105%" }}
                transition={spring.smooth}
                drag="x"
                dragListener={false}
                dragControls={drag}
                dragConstraints={{ left: 0, right: 0 }}
                dragElastic={{ left: 0.04, right: 0.6 }}
                onDragEnd={(_, info) => {
                  if (info.offset.x > 140 || info.velocity.x > 650) onOpenChange(false);
                }}
              >
                <div
                  className="flex cursor-grab items-start justify-between gap-4 border-b border-line px-5 pb-4 pt-3 active:cursor-grabbing"
                  onPointerDown={(e) => drag.start(e)}
                >
                  <div className="min-w-0 pt-1">
                    <Dialog.Title className="text-title font-semibold text-ink">{title}</Dialog.Title>
                    {description && <Dialog.Description className="mt-0.5 text-small text-ink-3">{description}</Dialog.Description>}
                  </div>
                  <Dialog.Close asChild>
                    <IconButton label="Close" onPointerDown={(e) => e.stopPropagation()}>
                      <X className="size-4" />
                    </IconButton>
                  </Dialog.Close>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
                {footer && <div className="border-t border-line px-5 py-3">{footer}</div>}
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
