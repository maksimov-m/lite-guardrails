import React, { useEffect, useState } from "react";
import * as api from "./api.js";

const PAGE = 50;

export default function LogsTab({ onError }) {
  const [logs, setLogs] = useState([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [module, setModule] = useState("");
  const [metaKeys, setMetaKeys] = useState([]);
  const [metaKey, setMetaKey] = useState("");
  const [metaValue, setMetaValue] = useState("");
  const [open, setOpen] = useState(() => new Set());

  const load = async (offset) => {
    try {
      const r = await api.getLogs(module || null, PAGE, offset, metaKey || null, metaValue || null);
      setLogs(r.logs);
      setHasMore(r.has_more);
      onError("");
    } catch (e) { onError(e.message); }
  };
  const loadKeys = async () => {
    try { setMetaKeys((await api.getMetaKeys()).keys); }
    catch (e) { onError(e.message); }
  };

  useEffect(() => { load(page * PAGE); }, [module, metaKey, page]);
  useEffect(() => { loadKeys(); }, []);

  // применить фильтр по значению metadata: всегда с первой страницы
  const apply = () => (page === 0 ? load(0) : setPage(0));
  const pick = (k, v) => { setMetaKey(k); setMetaValue(v); setPage(0); };
  const toggle = (id) => setOpen((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <select value={module} onChange={(e) => { setModule(e.target.value); setPage(0); }}>
          <option value="">все модули</option>
          <option value="pii">pii</option>
          <option value="nsfw">nsfw</option>
          <option value="relevant">relevant</option>
        </select>

        <span className="muted">metadata:</span>
        <select value={metaKey}
                onChange={(e) => { setMetaKey(e.target.value); setMetaValue(""); setPage(0); }}>
          <option value="">любой ключ</option>
          {metaKeys.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <input placeholder="значение (опц.)" value={metaValue} disabled={!metaKey}
               onChange={(e) => setMetaValue(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && apply()} style={{ maxWidth: 200 }} />

        <button onClick={() => { apply(); loadKeys(); }}>Обновить</button>
      </div>

      <table>
        <thead>
          <tr>
            <th style={{ width: 30 }} />
            <th style={{ width: 160 }}>время</th>
            <th style={{ width: 80 }}>модуль</th>
            <th style={{ width: 60 }}>мс</th>
            <th>результат</th>
            <th style={{ width: 220 }}>metadata</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((l) => (
            <LogRow key={l.id} log={l} expanded={open.has(l.id)}
                    onToggle={() => toggle(l.id)} onPick={pick} />
          ))}
          {logs.length === 0 && (
            <tr><td colSpan={6} className="muted">Запусков за выбранный фильтр нет. Смягчите фильтр или запустите проверку во вкладке «Демо».</td></tr>
          )}
        </tbody>
      </table>

      <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
        <button className="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
          ← Назад
        </button>
        <span className="muted">стр. {page + 1}</span>
        <button className="ghost" disabled={!hasMore} onClick={() => setPage((p) => p + 1)}>
          Вперёд →
        </button>
      </div>
    </div>
  );
}

// Одна строка лога: свёрнута до сводки; клик раскрывает вход/выход/metadata.
function LogRow({ log, expanded, onToggle, onPick }) {
  const { text, hit } = summarize(log.module, log.output);
  return (
    <>
      <tr onClick={onToggle} style={{ cursor: "pointer" }}>
        <td className="muted">{expanded ? "▾" : "▸"}</td>
        <td className="muted">{new Date(log.ts).toLocaleString()}</td>
        <td>{log.module}</td>
        <td>{log.duration_ms}</td>
        <td className={hit ? "danger-text" : "muted"}>{text}</td>
        <td><MetaCell meta={log.meta} onPick={onPick} /></td>
      </tr>
      {expanded && (
        <tr>
          <td />
          <td colSpan={5}>
            <div className="log-detail">
              <div className="muted">вход:</div>
              <div className="rule-val">{log.input || <span className="muted">—</span>}</div>
              <div className="muted" style={{ marginTop: 8 }}>выход:</div>
              <pre className="mono log-json">{pretty(log.output)}</pre>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// Короткая сводка результата: hit=true — гуард сработал (подсвечиваем).
function summarize(module, output) {
  let o;
  try { o = JSON.parse(output); } catch { return { text: String(output).slice(0, 80), hit: false }; }
  if (module === "pii") {
    const n = Array.isArray(o.data) ? o.data.length : 0;
    return o.PII_DETECT ? { text: `PII: ${n} сущностей`, hit: true } : { text: "чисто", hit: false };
  }
  if (module === "nsfw") {
    return o.NSFW_DETECT ? { text: "NSFW", hit: true } : { text: "чисто", hit: false };
  }
  if (module === "relevant") {
    return o.RELEVANT === false
      ? { text: "смолток / нерелевантно", hit: true }
      : { text: "релевантно", hit: false };
  }
  return { text: "", hit: false };
}

function pretty(output) {
  try { return JSON.stringify(JSON.parse(output), null, 2); }
  catch { return String(output); }
}

// Показывает пары key=value чипсами; клик по чипу подставляет их в фильтр.
function MetaCell({ meta, onPick }) {
  if (!meta || Object.keys(meta).length === 0) return <span className="muted">—</span>;
  return (
    <div className="words">
      {Object.entries(meta).map(([k, v]) => (
        <span className="word-chip" key={k} style={{ cursor: "pointer" }}
              title="фильтровать по этому значению"
              onClick={(e) => { e.stopPropagation(); onPick(k, String(v)); }}>
          {k}={String(v)}
        </span>
      ))}
    </div>
  );
}
