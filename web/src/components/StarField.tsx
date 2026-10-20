/**
 * StarField — animated canvas starfield with:
 *   · 260 stars across 3 parallax layers (depth via mouse)
 *   · Per-star twinkling via sine offset
 *   · Soft glow halo on the bigger/brighter ones
 *   · 4 slowly-drifting nebula blobs (radial colour clouds)
 *   · Occasional shooting meteors with gradient trail + head sparkle
 *   · Respects prefers-reduced-motion (static render, no meteors)
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
  r: number; g: number; b: number;
}

interface Meteor {
  x: number; y: number;
  vx: number; vy: number;
  trail: number; // normalised length (0–1)
  alpha: number;
  decay: number;
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

// Slowly drifting tinted clouds painted under the stars
const NEBULAE = [
  { r: 65,  g: 30,  b: 200, a: 0.07, cx: 0.12, cy: 0.18, ph: 0.00 },
  { r: 10,  g: 65,  b: 210, a: 0.06, cx: 0.82, cy: 0.88, ph: 2.10 },
  { r: 0,   g: 120, b: 200, a: 0.05, cx: 0.55, cy: 0.05, ph: 4.20 },
  { r: 140, g: 20,  b: 180, a: 0.05, cx: 0.28, cy: 0.78, ph: 1.55 },
];

const PARALLAX = [0.003, 0.007, 0.013] as const;

const rand = (lo: number, hi: number) => Math.random() * (hi - lo) + lo;

function buildStars(n: number): Star[] {
  return Array.from({ length: n }, () => {
    const [r, g, b] = COLORS[Math.floor(Math.random() * COLORS.length)];
    return {
      x: Math.random(), y: Math.random(),
      radius: rand(0.28, 1.95),
      baseAlpha: rand(0.22, 0.84),
      twinkleSpeed: rand(0.18, 1.15),
      twinklePhase: rand(0, Math.PI * 2),
      layer: Math.floor(Math.random() * 3) as 0 | 1 | 2,
      r, g, b,
    };
  });
}

/* ── component ────────────────────────────────────────────────────── */

export function StarField({ count = 260 }: { count?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const stars = buildStars(count);
    const meteors: Meteor[] = [];

    let W = 0, H = 0;
    let raf = 0;
    let t0 = 0;
    let nextMeteor = 0;

    // Smoothed mouse position (normalised)
    const mouse = { x: 0.5, y: 0.5 };
    const target = { x: 0.5, y: 0.5 };

    // ── resize ──────────────────────────────────────────────────────
    const resize = () => {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize, { passive: true });

    // ── mouse ────────────────────────────────────────────────────────
    const onMouse = (e: MouseEvent) => {
      target.x = e.clientX / window.innerWidth;
      target.y = e.clientY / window.innerHeight;
    };
    window.addEventListener("mousemove", onMouse, { passive: true });

    // ── main loop ────────────────────────────────────────────────────
    const tick = (t: DOMHighResTimeStamp) => {
      if (!t0) { t0 = t; nextMeteor = t + 4000; }
      const ms = t - t0;

      // Ease mouse
      if (!reduced) {
        mouse.x += (target.x - mouse.x) * 0.055;
        mouse.y += (target.y - mouse.y) * 0.055;
      }

      ctx.clearRect(0, 0, W, H);

      const mx = mouse.x - 0.5;
      const my = mouse.y - 0.5;

      /* ── nebula ─────────────────────────────────────────────────── */
      for (const n of NEBULAE) {
        const bx = (n.cx + (reduced ? 0 : Math.sin(ms * 0.000072 + n.ph) * 0.055)) * W;
        const by = (n.cy + (reduced ? 0 : Math.cos(ms * 0.000055 + n.ph) * 0.042)) * H;
        const rad = Math.max(W, H) * 0.58;
        const g2 = ctx.createRadialGradient(bx, by, 0, bx, by, rad);
        g2.addColorStop(0,    `rgba(${n.r},${n.g},${n.b},${n.a})`);
        g2.addColorStop(0.35, `rgba(${n.r},${n.g},${n.b},${+(n.a * 0.35).toFixed(4)})`);
        g2.addColorStop(1,    "rgba(0,0,0,0)");
        ctx.fillStyle = g2;
        ctx.fillRect(0, 0, W, H);
      }

      /* ── stars ──────────────────────────────────────────────────── */
      for (const s of stars) {
        const p  = PARALLAX[s.layer];
        const sx = (s.x + mx * p) * W;
        const sy = (s.y + my * p) * H;

        const tw = reduced ? 0 : Math.sin(ms * 0.001 * s.twinkleSpeed + s.twinklePhase);
        const a  = Math.max(0.04, Math.min(1, s.baseAlpha + tw * 0.27));

        ctx.beginPath();
        ctx.arc(sx, sy, s.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${s.r},${s.g},${s.b},${a.toFixed(3)})`;
        ctx.fill();

        // Soft glow halo on bigger / brighter stars
        if (s.radius > 1.1 && a > 0.48) {
          const gr = ctx.createRadialGradient(sx, sy, 0, sx, sy, s.radius * 4.5);
          gr.addColorStop(0, `rgba(${s.r},${s.g},${s.b},${+(a * 0.3).toFixed(3)})`);
          gr.addColorStop(1, "rgba(0,0,0,0)");
          ctx.beginPath();
          ctx.arc(sx, sy, s.radius * 4.5, 0, Math.PI * 2);
          ctx.fillStyle = gr;
          ctx.fill();
        }
      }

      /* ── meteors ────────────────────────────────────────────────── */
      if (!reduced && t >= nextMeteor) {
        const angle = rand(22, 55) * Math.PI / 180;
        meteors.push({
          x: rand(0.04, 0.68), y: rand(0.02, 0.44),
          vx: Math.cos(angle) * rand(0.0011, 0.002),
          vy: Math.sin(angle) * rand(0.0011, 0.002),
          trail: rand(0.07, 0.14),
          alpha: 1,
          decay: rand(0.010, 0.018),
        });
        nextMeteor = t + rand(6000, 16000);
      }

      for (let i = meteors.length - 1; i >= 0; i--) {
        const m = meteors[i];
        m.x    += m.vx;
        m.y    += m.vy;
        m.alpha -= m.decay;

        if (m.alpha <= 0 || m.x > 1.12 || m.y > 1.12) {
          meteors.splice(i, 1);
          continue;
        }

        const len = Math.hypot(m.vx, m.vy);
        const nx  = m.vx / len;
        const ny  = m.vy / len;

        const x1 = m.x * W, y1 = m.y * H;
        const x2 = (m.x - nx * m.trail) * W;
        const y2 = (m.y - ny * m.trail) * H;

        // Trail gradient
        const tg = ctx.createLinearGradient(x2, y2, x1, y1);
        tg.addColorStop(0,    "rgba(255,255,255,0)");
        tg.addColorStop(0.72, `rgba(210,230,255,${+(m.alpha * 0.5).toFixed(3)})`);
        tg.addColorStop(1,    `rgba(255,255,255,${m.alpha.toFixed(3)})`);

        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x1, y1);
        ctx.strokeStyle = tg;
        ctx.lineWidth   = 1.7;
        ctx.stroke();

        // Head sparkle
        const hg = ctx.createRadialGradient(x1, y1, 0, x1, y1, 6);
        hg.addColorStop(0, `rgba(220,238,255,${+(m.alpha * 0.88).toFixed(3)})`);
        hg.addColorStop(1, "rgba(0,0,0,0)");
        ctx.beginPath();
        ctx.arc(x1, y1, 6, 0, Math.PI * 2);
        ctx.fillStyle = hg;
        ctx.fill();
      }

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize",    resize);
      window.removeEventListener("mousemove", onMouse);
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
