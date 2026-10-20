import type { Transition, Variants } from "motion/react";

/** Spring presets — every motion in the app uses one of these so physics feel like one system. */
export const spring = {
  /** controls, toggles, indicators: fast, no visible overshoot */
  snappy: { type: "spring", stiffness: 520, damping: 38, mass: 0.7 } as Transition,
  /** panels, sheets, layout changes */
  smooth: { type: "spring", stiffness: 300, damping: 32, mass: 0.9 } as Transition,
  /** something arriving: finished section landing, step completing */
  land: { type: "spring", stiffness: 420, damping: 24, mass: 0.8 } as Transition,
  /** numbers counting to a value */
  counter: { stiffness: 120, damping: 24, mass: 1 },
  /** delight bounce: icon reactions, drop confirms */
  elastic: { type: "spring", stiffness: 380, damping: 16, mass: 0.8 } as Transition,
  /** instant micro-feedback: hover lifts */
  quick: { type: "spring", stiffness: 700, damping: 44, mass: 0.4 } as Transition,
};

/** Press feedback for anything clickable. */
export const press = { whileTap: { scale: 0.97 }, transition: spring.snappy };

/** Page enter/exit — scale + fade gives spatial depth. */
export const pageVariants: Variants = {
  initial: { opacity: 0, y: 12, scale: 0.993 },
  animate: { opacity: 1, y: 0, scale: 1, transition: spring.smooth },
  exit: { opacity: 0, y: -6, scale: 0.997, transition: { duration: 0.14, ease: "easeIn" } },
};

/** Stagger container — wrap a list; children use listItemVariants. */
export const listVariants: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.055, delayChildren: 0.03 } },
};

/** Stagger child — pair with listVariants on the parent. */
export const listItemVariants: Variants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: spring.smooth },
};

/** Simple fade-up for section headers, stats, hero text. */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: spring.smooth },
};
