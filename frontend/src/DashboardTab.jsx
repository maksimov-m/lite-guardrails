import React, { useEffect, useState } from "react";
import * as api from "./api.js";

const PERIODS = [
  { key: "1h", label: "1 час" },
  { key: "24h", label: "24 часа" },
  { key: "7d", label: "7 дней" },
];

const MODULE_TITLES = { pii: "PII", nsfw: "NSFW", relevant: "Relevant" };

// Входная страница: сводка по работе гуарда за период. Метрики считаются
// на сервере SQL-агрегацией по логам — хот-путь детекции не затрагивается.
export default function DashboardTab({ onError }) {
  const [period, setPeriod] = useState("24h");
  const [stats, setStats] = useState(null);

  const load = async (p = period) => {
    try { setStats(await api.getStats(p)); onError(""); }
    catch (e) { onError(e.message); }
  };
  useEffect(() => { load(period); }, [period]);

  if (!stats) return <p className="muted">Загрузка…</p>;

  const totalRuns = stats.modules.reduce((s, m) => s + m.runs, 0);
  const totalDet = stats.modules.reduce((s, m) => s + m.detections, 0);

  return (
    <div>
      <div className="row" style={{ marginBottom: 16 }}>
        <div className="segment">
          {PERIODS.map((p) => (
            <button key={p.key} className={p.key === period ? "active" : ""}
                    onClick={() => setPeriod(p.key)}>
              {p.label}
            </button>
          ))}
        </div>
        <button onClick={() => load()}>Обновить</button>
        <span className="muted">
          всего: {totalRuns} запусков · {totalDet} детекций
        </span>
      </div>

      <div className="row" style={{ alignItems: "stretch", flexWrap: "wrap" }}>
        {stats.modules.map((m) => <ModuleCard key={m.module} m={m} />)}
        {stats.modules.length === 0 && (
          <div className="card" style={{ flex: 1 }}>
            <p className="muted" style={{ margin: 0 }}>
              За этот период запусков не было.
            </p>
          </div>
        )}
      </div>

      <Timeline timeline={stats.timeline} />

      <div className="row" style={{ alignItems: "stretch", flexWrap: "wrap" }}>
        <TopList title="Топ потребителей (api-ключи)" rows={stats.top_keys}
                 label={(r) => r.name} value={(r) => r.runs} noun="запусков" />
        <TopList title="Что ловит PII" rows={stats.pii_classes}
                 label={(r) => r.class} value={(r) => r.count} noun="находок" />
      </div>
    </div>
  );
}

function ModuleCard({ m }) {
  const rate = m.runs ? Math.round((m.detections / m.runs) * 100) : 0;
  return (
    <div className="card" style={{ flex: 1, minWidth: 220 }}>
      <div className="group-h">{MODULE_TITLES[m.module] || m.module}</div>
      <div className="stat">
        <span className="stat-num">{m.runs}</span>
        <span className="stat-label">запусков</span>
      </div>
      <div style={{ marginTop: 12 }}>
        {m.detections} детекций <span className="muted">({rate}%)</span>
      </div>
      <div className="muted mono" style={{ marginTop: 4, fontSize: 12 }}>
        avg {m.avg_ms} мс · p95 {m.p95_ms} мс
      </div>
    </div>
  );
}

// Бар-чарт на чистом CSS: высота столбика = доля от максимума за период,
// закрашенная нижняя часть — детекции.
function Timeline({ timeline }) {
  const max = Math.max(1, ...timeline.map((t) => t.runs));
  return (
    <div className="card">
      <div className="group-h">Запуски и детекции по времени</div>
      {timeline.length === 0 && <p className="muted" style={{ margin: 0 }}>нет данных</p>}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 120 }}>
        {timeline.map((t) => (
          <div key={t.ts} title={`${new Date(t.ts).toLocaleString()}\n${t.runs} запусков, ${t.detections} детекций`}
               style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", height: "100%" }}>
            <div style={{
              height: `${(t.runs / max) * 100}%`,
              minHeight: 2,
              background: "var(--border)",
              borderRadius: 2,
              position: "relative",
              overflow: "hidden",
            }}>
              <div style={{
                position: "absolute", bottom: 0, left: 0, right: 0,
                height: `${t.runs ? (t.detections / t.runs) * 100 : 0}%`,
                background: "var(--accent)",
              }} />
            </div>
          </div>
        ))}
      </div>
      {timeline.length > 0 && (
        <div className="row muted" style={{ justifyContent: "space-between", marginTop: 6 }}>
          <span>{new Date(timeline[0].ts).toLocaleString()}</span>
          <span>серым — запуски, синим — детекции</span>
          <span>{new Date(timeline[timeline.length - 1].ts).toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}

function TopList({ title, rows, label, value, noun }) {
  const max = Math.max(1, ...rows.map(value));
  return (
    <div className="card" style={{ flex: 1, minWidth: 260 }}>
      <div className="group-h">{title}</div>
      {rows.length === 0 && <p className="muted" style={{ margin: 0 }}>нет данных</p>}
      {rows.map((r) => (
        <div key={label(r)} style={{ marginBottom: 6 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>{label(r)}</span>
            <span className="muted">{value(r)} {noun}</span>
          </div>
          <div style={{ height: 6, background: "var(--border)", borderRadius: 2 }}>
            <div style={{ height: "100%", width: `${(value(r) / max) * 100}%`,
                          background: "var(--accent)", borderRadius: 2 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
