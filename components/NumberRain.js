"use client";
import { useEffect, useRef } from "react";

// Full-viewport canvas of faint flickering digits — the "machine substrate"
// backdrop. Cheap: one rAF loop, ~2% of cells mutate per frame.
export default function NumberRain() {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    const CELL = 26;
    const CHARS = "0123456789";
    let cols = 0, rows = 0, grid = [];
    let raf;

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      cols = Math.ceil(canvas.width / CELL);
      rows = Math.ceil(canvas.height / CELL);
      grid = [];
      for (let i = 0; i < cols * rows; i++) {
        grid.push({
          ch: CHARS[(Math.random() * 10) | 0],
          a: Math.random() * 0.14,        // current alpha
          target: Math.random() * 0.14,   // alpha it's drifting toward
          hot: false,
        });
      }
    }

    function frame() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.font = "13px ui-monospace, Menlo, monospace";
      const n = grid.length;

      // mutate a small random sample each frame
      const mutations = Math.max(8, (n * 0.02) | 0);
      for (let m = 0; m < mutations; m++) {
        const cell = grid[(Math.random() * n) | 0];
        cell.ch = CHARS[(Math.random() * 10) | 0];
        cell.target = Math.random() * 0.14;
        // rare bright "signal" cells
        if (Math.random() < 0.02) { cell.target = 0.55; cell.hot = true; }
        else cell.hot = false;
      }

      for (let i = 0; i < n; i++) {
        const cell = grid[i];
        cell.a += (cell.target - cell.a) * 0.08;
        if (cell.a < 0.008) continue;
        const x = (i % cols) * CELL + 6;
        const y = ((i / cols) | 0) * CELL + 16;
        ctx.fillStyle = cell.hot
          ? `rgba(0, 229, 199, ${cell.a})`
          : `rgba(110, 150, 170, ${cell.a})`;
        ctx.fillText(cell.ch, x, y);
      }
      raf = requestAnimationFrame(frame);
    }

    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="rain" aria-hidden="true" />;
}
