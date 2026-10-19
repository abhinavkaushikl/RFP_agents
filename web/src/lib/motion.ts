import type { Transition } from "motion/react";

/** Spring presets. Every motion in the app uses one of these so the physics feel like one system. */
export const spring = {
  /** controls, toggles, indicators: fast, no overshoot you can see */
  snappy: { type: "spring", stiffness: 520, damping: 38, mass: 0.7 } as Transition,
  /** panels, sheets, layout changes */
  smooth: { type: "spring", stiffness: 300, damping: 32, mass: 0.9 } as Transition,
  /** something arriving: a finished section landing, a step completing */
  land: { type: "spring", stiffness: 420, damping: 24, mass: 0.8 } as Transition,
  /** numbers counting to a value */
  counter: { stiffness: 120, damping: 24, mass: 1 },
};

/** Press feedback for anything clickable. */
export const press = { whileTap: { scale: 0.97 }, transition: spring.snappy };

export const pageVariants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0, transition: spring.smooth },
  exit: { opacity: 0, y: -4, transition: { duration: 0.12 } },
};
