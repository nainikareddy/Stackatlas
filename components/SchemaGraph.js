"use client";

const W = 190, H = 46;

function statusClass(s) {
  return s === "critical" ? "crit" : s === "warning" ? "warn" : "ok";
}

export default function SchemaGraph({ tables, edges, selected, onSelect }) {
  const byName = Object.fromEntries(tables.map((t) => [t.name, t]));

  return (
    <div className="graph-wrap">
      <svg viewBox="0 0 1240 500" xmlns="http://www.w3.org/2000/svg">
        {/* edges under nodes */}
        {edges.map((e, i) => {
          const a = byName[e.from], b = byName[e.to];
          if (!a || !b) return null;
          const x1 = a.pos.x + W / 2, y1 = a.pos.y + H / 2;
          const x2 = b.pos.x + W / 2, y2 = b.pos.y + H / 2;
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - 24;
          const cls = e.broken ? "edge broken" : e.enforced ? "edge" : "edge soft";
          return (
            <path key={i} className={cls} d={`M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`} />
          );
        })}
        {tables.map((t) => (
          <g
            key={t.name}
            className={`node ${statusClass(t.status)}${selected === t.name ? " sel" : ""}`}
            transform={`translate(${t.pos.x}, ${t.pos.y})`}
            onClick={() => onSelect(t.name)}
          >
            <rect width={W} height={H} />
            <circle className="dot" cx="16" cy={H / 2} r="4" />
            <text x="30" y="20">{t.name}</text>
            <text className="rows" x="30" y="36">
              {t.rows} rows · {t.readsPerDay.toLocaleString()} r/d
            </text>
          </g>
        ))}
      </svg>
      <div className="legend">
        <span><i style={{ borderColor: "var(--line-strong)" }} />enforced FK</span>
        <span><i style={{ borderColor: "rgba(107,128,144,0.5)", borderTopStyle: "dashed" }} />inferred join (no FK)</span>
        <span><i style={{ borderColor: "var(--magenta)", borderTopStyle: "dashed" }} />broken FK</span>
      </div>
    </div>
  );
}
