"use client";
import { useEffect, useRef, useState } from "react";
import { agentAnswers } from "../data/catalog";

function findAnswer(query) {
  const q = query.toLowerCase();
  let best = null, bestScore = 0;
  for (const item of agentAnswers) {
    const score = item.match.filter((kw) => q.includes(kw)).length;
    if (score > bestScore) { best = item; bestScore = score; }
  }
  return best
    ? best.a
    : "No high-confidence match in the catalog for that question. Try asking about a specific table or column — e.g. \"What does orders_v2.status mean?\" (The live MCP server does full semantic search; this demo console uses the same catalog with keyword matching.)";
}

export default function AgentConsole() {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState([]);
  const [typing, setTyping] = useState(null); // { q, full, shown }
  const timer = useRef(null);

  useEffect(() => () => clearInterval(timer.current), []);

  function ask(q) {
    if (!q.trim() || typing) return;
    const full = findAnswer(q);
    setInput("");
    setTyping({ q, full, shown: "" });
    let i = 0;
    clearInterval(timer.current);
    timer.current = setInterval(() => {
      i += 3;
      if (i >= full.length) {
        clearInterval(timer.current);
        setHistory((h) => [...h, { q, a: full }]);
        setTyping(null);
      } else {
        setTyping({ q, full, shown: full.slice(0, i) });
      }
    }, 12);
  }

  return (
    <div className="panel console">
      <div className="panel-hd">
        <span>Agent Context Query</span>
        <span className="hint">scripted demo — the live agent demo is Claude + MCP, not this panel</span>
      </div>
      <div className="chips">
        {agentAnswers.map((item) => (
          <button key={item.q} className="chip" onClick={() => ask(item.q)}>
            {item.q}
          </button>
        ))}
      </div>
      <div className="qa">
        {history.map((h, i) => (
          <div key={i}>
            <div className="q-line">&gt; <b>{h.q}</b></div>
            <div className="a-line">{h.a}</div>
          </div>
        ))}
        {typing && (
          <div>
            <div className="q-line">&gt; <b>{typing.q}</b></div>
            <div className="a-line">
              {typing.shown}
              <span className="cursor" />
            </div>
          </div>
        )}
      </div>
      <div className="input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(input)}
          placeholder="Ask the catalog anything about this database..."
        />
        <button onClick={() => ask(input)}>QUERY</button>
      </div>
    </div>
  );
}
