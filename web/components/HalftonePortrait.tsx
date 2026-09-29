type Blob = { cx: number; cy: number; rx: number; ry: number; w: number };

const SHAPE: Blob[] = [
  { cx: 210, cy: 260, rx: 175, ry: 240, w: 1.05 },
  { cx: 260, cy: 140, rx: 180, ry: 130, w: 1.15 },
  { cx: 170, cy: 190, rx: 110, ry: 150, w: 0.9  },
  { cx: 305, cy: 210, rx: 105, ry: 190, w: 1.0  },
  { cx: 230, cy: 430, rx: 175, ry: 105, w: 1.0  },
  { cx: 340, cy: 330, rx:  95, ry: 150, w: 0.7  },
  { cx: 140, cy: 340, rx:  85, ry: 130, w: 0.7  },
  { cx: 260, cy: 520, rx: 155, ry:  70, w: 0.9  },
];

function density(x: number, y: number): number {
  let d = 0;
  for (const b of SHAPE) {
    const dx = (x - b.cx) / b.rx;
    const dy = (y - b.cy) / b.ry;
    const inside = 1 - Math.sqrt(dx * dx + dy * dy);
    if (inside > 0) d = Math.max(d, inside * b.w);
  }
  return d;
}

export function HalftonePortrait() {
  const W = 480;
  const H = 640;
  const step = 8;
  const dots: JSX.Element[] = [];

  for (let y = 0; y < H; y += step) {
    for (let x = 0; x < W; x += step) {
      const ox = x + ((y / step) % 2 === 0 ? 0 : step / 2);
      const d = density(ox, y);
      if (d <= 0.02) continue;
      const jitter = ((ox * 31 + y * 17) % 100) / 100;
      const eased = Math.pow(d, 0.85);
      const r = Math.min(step / 2 - 0.1, eased * (step / 2) * (0.9 + jitter * 0.15));
      if (r < 0.4) continue;
      dots.push(
        <circle key={`${x}-${y}`} cx={ox} cy={y} r={r} />
      );
    }
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid slice"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="halftone-portrait"
    >
      <g fill="var(--ink)">{dots}</g>
    </svg>
  );
}
