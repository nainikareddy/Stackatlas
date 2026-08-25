"use client";
import { useState } from "react";
import { catalog } from "../data/catalog";
import NumberRain from "../components/NumberRain";
import SchemaGraph from "../components/SchemaGraph";
import AgentConsole from "../components/AgentConsole";

export default function Home() {
  const [selected, setSelected] = useState("orders_v2");
  const table = catalog.tables.find((t) => t.name === selected);
  const { stats } = catalog;

  return (
    <>
      <NumberRain />
      <main className="app">
        <header className="hdr">
          <div>
            <h1>STACK<span>ATLAS</span></h1>
            <div className="sub">THE CONTEXT LAYER FOR AI AGENTS</div>
          </div>
          <div className="db">◉ {catalog.database}</div>
        </header>

        <section className="stats">
          <div className="stat">
            <div className="k">Health Score</div>
            <div className={`v ${catalog.healthScore >= 80 ? "good" : catalog.healthScore >= 60 ? "warn" : "bad"}`}>
              {catalog.healthScore}<span style={{ fontSize: 13, color: "var(--text-dim)" }}>/100</span>
            </div>
          </div>
          <div className="stat">
            <div className="k">Tables / Columns</div>
            <div className="v">{stats.tables} / {stats.columns}</div>
          </div>
          <div className="stat">
            <div className="k">Doc Coverage</div>
            <div className="v good">{Math.round(stats.docCoverage * 100)}%</div>
          </div>
          <div className="stat">
            <div className="k">FK Coverage</div>
            <div className="v bad">{Math.round(stats.fkCoverage * 100)}%</div>
          </div>
          <div className="stat">
            <div className="k">Orphaned Tables</div>
            <div className="v bad">{stats.orphans}</div>
          </div>
        </section>

        <section className="grid">
          <div className="panel">
            <div className="panel-hd">
              <span>Schema Graph</span>
              <span className="hint">click a table</span>
            </div>
            <SchemaGraph
              tables={catalog.tables}
              edges={catalog.edges}
              selected={selected}
              onSelect={setSelected}
            />
          </div>

          <div className="panel detail">
            <div className="panel-hd"><span>Table Intelligence</span></div>
            {table && (
              <div className="detail-body">
                <h3>{table.name}</h3>
                <div className="traffic">
                  {table.rows} rows · {table.readsPerDay.toLocaleString()} reads/day · {table.writesPerDay.toLocaleString()} writes/day
                </div>
                <div className="docline">{table.doc}</div>
                {table.issues.map((iss, i) => (
                  <div key={i} className={`issue${table.status === "critical" ? " crit-issue" : ""}`}>⚠ {iss}</div>
                ))}
                <table className="cols">
                  <tbody>
                    {table.columns.map((c) => (
                      <tr key={c.name}>
                        <td className={`cn${c.flag ? " flag" : ""}`}>{c.name}</td>
                        <td className="ct">{c.type}</td>
                        <td className="cd">{c.doc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        <AgentConsole />

        <footer className="foot">
          catalog generated {new Date(catalog.generatedAt).toUTCString()} · introspection + Claude docgen + MCP ·{" "}
          <a href="https://github.com" onClick={(e) => e.preventDefault()}>stackatlas</a>
        </footer>
      </main>
    </>
  );
}
