/**
 * StarField — a calm animated canvas starfield behind the app:
 *   · 140 stars across 3 parallax layers (depth via mouse)
 *   · Gentle per-star twinkling via sine offset
 *   · Soft glow halo on the bigger/brighter ones (pre-drawn sprites)
 *   · 4 tinted nebula clouds, painted once per resize rather than every frame
 *   · A rare shooting meteor with gradient trail + head sparkle
 *
 * Kept cheap on purpose: the sidebar and header blur whatever is behind them, so every
 * repaint here also costs a re-blur there.
 *   · ~30 fps while the pointer moves or a meteor is flying, ~8 fps otherwise
 *   · One static frame in light mode (stars sit at 8% opacity there) and for
 *     prefers-reduced-motion
 */

import { useEffect, useRef } from "react";

/* ── types ────────────────────────────────────────────────────────── */

interface Star {
  x: number; y: number; // normalised 0–1
  radius: number;
  baseAlpha: number;
  twinkleSpeed: number;
  twinklePhase: number;
  layer: 0 | 1 | 2; // 0=far · 1=mid · 2=near
  color: string; // precomputed so a frame allocates no strings
  sprite: number; // index into COLORS / glow sprites
}

interface Meteor {
  x: number; y: number;
  vx: number; vy: number; // normalised units per ms
  trail: number; // normalised length (0–1)
  alpha: number;
  decay: number; // alpha per ms
}

/* ── data ─────────────────────────────────────────────────────────── */

const COLORS: [number, number, number][] = [
  [255, 255, 255],
  [255, 255, 255],
  [255, 255, 255],
  [210, 225, 255], // blue-white (hot)
  [210, 225, 255],
  [255, 240, 215], // warm (cool)
  [180, 210, 255], // soft blue
];

// Faint tinted clouds painted under the stars
const NEBULAE = [
  { r: 65,  g: 30,  b: 200, a: 0.07, cx: 0.12, cy: 0.18 },
  { r: 10,  g: 65,  b: 210, a: 0.06, cx: 0.82, cy: 0.88 },
  { r: 0,   g: 120, b: 200, a: 0.05, cx: 0.55, cy: 0.05 },
  { r: 140, g: 20,  b: 180, a: 0.05, cx: 0.28, cy: 0.78 },
];

const PARALLAX = [0.003, 0.007, 0.013] as const;

const ACTIVE_FRAME_MS = 33; // ~30 fps
const IDLE_FRAME_MS = 125; // ~8 fps
const IDLE_AFTER_MS = 4000; // no pointer movement for this long counts as idle
const TWINKLE = 0.16; // twinkle amplitude on top of each star's base alpha

const rand = (lo: number, hi: number) => Math.random() * (hi - lo) + lo;

function buildStars(n: number): Star[] {
  return Array.from({ length: n }, () => {
    const sprite = Math.floor(Math.random() * COLORS.length);
    const [r, g, b] = COLORS[sprite];
    return {
      x: Math.random(), y: Math.random(),
      radius: rand(0.28, 1.8),
      baseAlpha: rand(0.18, 0.72),
      twinkleSpeed: rand(0.12, 0.7),
      twinklePhase: rand(0, Math.PI * 2),
      layer: Math.floor(Math.random() * 3) as 0 | 1 | 2,
      color: `rgb(${r},${g},${b})`,
      sprite,
    };
  });
}

/** A soft round glow in one colour, drawn once and stamped with drawImage. */
function glowSprite([r, g, b]: [number, number, number]): HTMLCanvasElement {
  const size = 32;
  const sprite = document.createElement("canvas");
  sprite.width = sprite.height = size;
  const sctx = sprite.getContext("2d")!;
  const gr = sctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gr.addColorStop(0, `rgba(${r},${g},${b},1)`);
  gr.addColorStop(1, `rgba(${r},${g},${b},0)`);
  sctx.fillStyle = gr;
  sctx.fillRect(0, 0, size, size);
  return sprite;
}

/** The nebula layer for one viewport size. */
function paintNebulae(W: number, H: number): HTMLCanvasElement {
  const layer = document.createElement("canvas");
  layer.width = W;
  layer.height = H;
  const lctx = layer.getContext("2d")!;
  const rad = Math.max(W, H) * 0.58;
  for (const n of NEBULAE) {
    const bx = n.cx * W;
    const by = n.cy * H;
    const g2 = lctx.createRadialGradient(bx, by, 0, bx, by, rad);
    g2.addColorStop(0,    `rgba(${n.r},${n.g},${n.b},${n.a})`);
    g2.addColorStop(0.35, `rgba(${n.r},${n.g},${n.b},${+(n.a * 0.35).toFixed(4)})`);
    g2.addColorStop(1,    "rgba(0,0,0,0)");
    lctx.fillStyle = g2;
    lctx.fillRect(0, 0, W, H);
  }
  return layer;
}

/* ── component ────────────────────────────────────────────────────── */

export function StarField({ count = 140 }: { count?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const stars = buildStars(count);
    const sprites = COLORS.map(glowSprite);
    const meteors: Meteor[] = [];

    let W = 0, H = 0;
    let nebula: HTMLCanvasElement | null = null;
    let raf = 0;
    let timer = 0;
    let running = false;
    let sleeping = false; // waiting out an idle-rate frame
    let t0 = 0;
    let last = 0;
    let nextMeteor = 0;
    let lastPointer = -Infinity;

    // Smoothed mouse position (normalised)
    const mouse = { x: 0.5, y: 0.5 };
    const target = { x: 0.5, y: 0.5 };

    // ── draw one frame ───────────────────────────────────────────────
    const draw = (ms: number) => {
      ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = 1;
      if (nebula) ctx.drawImage(nebula, 0, 0);

      const mx = mouse.x - 0.5;
      const my = mouse.y - 0.5;

      /* ── stars ──────────────────────────────────────────────────── */
      for (const s of stars) {
        const p  = PARALLAX[s.layer];
        const sx = (s.x + mx * p) * W;
        const sy = (s.y + my * p) * H;

        const tw = reduced ? 0 : Math.sin(ms * 0.001 * s.twinkleSpeed + s.twinklePhase);
        const a  = Math.max(0.04, Math.min(1, s.baseAlpha + tw * TWINKLE));

        ctx.globalAlpha = a;
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(sx, sy, s.radius, 0, Math.PI * 2);
        ctx.fill();

        // Soft glow halo on bigger / brighter stars
        if (s.radius > 1.1 && a > 0.48) {
          const halo = s.radius * 4.5;
          ctx.globalAlpha = a * 0.3;
          ctx.drawImage(sprites[s.sprite], sx - halo, sy - halo, halo * 2, halo * 2);
        }
      }

      /* ── meteors ────────────────────────────────────────────────── */
      for (const m of meteors) {
        const len = Math.hypot(m.vx, m.vy);
        const nx  = m.vx / len;
        const ny  = m.vy / len;

        const x1 = m.x * W, y1 = m.y * H;
        const x2 = (m.x - nx * m.trail) * W;
        const y2 = (m.y - ny * m.trail) * H;

        // Trail gradient (one per meteor, and meteors are rare)
        const tg = ctx.createLinearGradient(x2, y2, x1, y1);
        tg.addColorStop(0,    "rgba(255,255,255,0)");
        tg.addColorStop(0.72, `rgba(210,230,255,${+(m.alpha * 0.5).toFixed(3)})`);
        tg.addColorStop(1,    `rgba(255,255,255,${m.alpha.toFixed(3)})`);

        ctx.globalAlpha = 1;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x1, y1);
        ctx.strokeStyle = tg;
        ctx.lineWidth   = 1.5;
        ctx.stroke();

        // Head sparkle
        ctx.globalAlpha = m.alpha * 0.85;
        ctx.drawImage(sprites[3], x1 - 6, y1 - 6, 12, 12);
      }

      ctx.globalAlpha = 1;
    };

    const drawStatic = () => draw(t0 ? performance.now() - t0 : 0);

    // ── advance the simulation by dt ms ──────────────────────────────
    const step = (t: number, dt: number) => {
      // Same easing feel at any frame rate
      const k = 1 - Math.pow(1 - 0.055, dt / 16.7);
      mouse.x += (target.x - mouse.x) * k;
      mouse.y += (target.y - mouse.y) * k;

      if (t >= nextMeteor) {
        const angle = rand(22, 55) * Math.PI / 180;
        const speed = rand(0.0011, 0.002) / 16.7;
        meteors.push({
          x: rand(0.04, 0.68), y: rand(0.02, 0.44),
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          trail: rand(0.07, 0.14),
          alpha: 1,
          decay: rand(0.010, 0.018) / 16.7,
        });
        nextMeteor = t + rand(15000, 35000);
      }

      for (let i = meteors.length - 1; i >= 0; i--) {
        const m = meteors[i];
        m.x     += m.vx * dt;
        m.y     += m.vy * dt;
        m.alpha -= m.decay * dt;
        if (m.alpha <= 0 || m.x > 1.12 || m.y > 1.12) meteors.splice(i, 1);
      }
    };

    // ── main loop: a timer between frames, so idle stretches run nothing ──
    const tick = (t: DOMHighResTimeStamp) => {
      if (!t0) { t0 = t; nextMeteor = t + 8000; }
      const dt = last ? Math.min(t - last, 250) : 16.7;
      last = t;

      step(t, dt);
      draw(t - t0);
      if (!running) return;

      const active = meteors.length > 0 || t - lastPointer < IDLE_AFTER_MS;
      sleeping = !active;
      // rAF lands on the next vsync after the timer, so aim a little early
      const wait = (active ? ACTIVE_FRAME_MS : IDLE_FRAME_MS) - (performance.now() - t) - 8;
      timer = window.setTimeout(() => { raf = requestAnimationFrame(tick); }, Math.max(0, wait));
    };

    const start = () => {
      if (running || reduced) return;
      running = true;
      last = 0;
      raf = requestAnimationFrame(tick);
    };
    const stop = () => {
      running = false;
      sleeping = false;
      window.clearTimeout(timer);
      cancelAnimationFrame(raf);
    };

    // ── resize ──────────────────────────────────────────────────────
    const resize = () => {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
      nebula = paintNebulae(W, H);
      if (!running) drawStatic();
    };

    // ── mouse ────────────────────────────────────────────────────────
    const onPointer = (e: PointerEvent) => {
      target.x = e.clientX / window.innerWidth;
      target.y = e.clientY / window.innerHeight;
      lastPointer = performance.now();
      if (sleeping) {
        // Leave the idle rate right away instead of finishing the long wait
        sleeping = false;
        window.clearTimeout(timer);
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(tick);
      }
    };

    // ── theme: animate only in dark mode ─────────────────────────────
    const syncTheme = () => {
      if (document.documentElement.dataset.theme === "light") {
        stop();
        drawStatic();
      } else {
        start();
      }
    };
    const themeObserver = new MutationObserver(syncTheme);

    resize();
    window.addEventListener("resize", resize, { passive: true });
    if (!reduced) {
      window.addEventListener("pointermove", onPointer, { passive: true });
      themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
      syncTheme();
    }

    return () => {
      stop();
      themeObserver.disconnect();
      window.removeEventListener("resize",      resize);
      window.removeEventListener("pointermove", onPointer);
    };
  }, [count]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="star-field pointer-events-none fixed inset-0"
      style={{ zIndex: 0 }}
    />
  );
}
