"use client";
import { useEffect, useRef } from "react";

/** Faint topographic contours behind Today: the app's one decorative element. */
export default function Topo() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const draw = () => {
      const ctx = cv.getContext("2d");
      const box = cv.parentElement?.getBoundingClientRect();
      if (!ctx || !box) return;
      const dpr = window.devicePixelRatio || 1;
      cv.width = Math.max(1, box.width * dpr);
      cv.height = Math.max(1, box.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, box.width, box.height);
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--contour").trim() || "#ccc";
      const cx = box.width * 0.88, cy = Math.min(box.height, 760) * 0.95;
      for (let i = 1; i <= 15; i++) {
        ctx.beginPath();
        for (let a = 0; a <= Math.PI * 2 + 0.05; a += 0.05) {
          const r = i * 27 * (1 + 0.16 * Math.sin(a * 3 + i * 0.5) + 0.08 * Math.sin(a * 5 - i));
          const x = cx + Math.cos(a) * r * 1.35, y = cy + Math.sin(a) * r * 0.8;
          if (a === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.globalAlpha = Math.max(0.15, 0.9 - i * 0.05);
        ctx.stroke();
      }
    };
    draw();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    window.addEventListener("resize", draw);
    mq.addEventListener("change", draw);
    return () => { window.removeEventListener("resize", draw); mq.removeEventListener("change", draw); };
  }, []);
  return <canvas ref={ref} className="topo" aria-hidden="true" />;
}
