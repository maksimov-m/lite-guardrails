import React, { useEffect, useState } from "react";
import * as api from "./api.js";

export default function LogsTab({ onError }) {
  const [logs, setLogs] = useState([]);
  const [module, setModule] = useState("");
  const [metaKeys, setMetaKeys] = useState([]);
  const [metaKey, setMetaKey] = useState("");
  const [metaValue, setMetaValue] = useState("");

  const load = async () => {
    try {
      const r = await api.getLogs(module || null, 100, metaKey || null, metaValue || null);
      setLogs(r.logs);
      onError("");
    } catch (e) { onError(e.message); }
  };
  const loadKeys = async () => {
    try { setMetaKeys((await api.getMetaKeys()).keys); }
    catch (e) { onError(e.message); }
  };

  useEffect(() => { load(); }, [module, metaKey]);
  useEffect(() => { loadKeys(); }, []);

  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <select value={module} onChange={(e) => setModule(e.target.value)}>
          <option value="">все модули</option>
          <option value="pii">pii</option>
          <option value="nsfw">nsfw</option>
          <option value="relevant">relevant</option>
        </select>

        <span className="muted">metadata:</span>
        <select value={metaKey} onChange={(e) => { setMetaKey(e.target.value); setMetaValue(""); }}>
          <option value="">любой ключ</option>
          {metaKeys.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <input placeholder="значение (опц.)" value={metaValue} disabled={!metaKey}
               onChange={(e) => setMetaValue(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && load()} style={{ maxWidth: 200 }} />

        <button onClick={() => { load(); loadKeys(); }}>Обновить</button>
      </div>
      <table>
        <thead>
          <tr>
            <th style={{ width: 150 }}>время</th>
            <th style={{ width: 80 }}>модуль</th>
            <th style={{ width: 60 }}>мс</th>
            <th style={{ width: 180 }}>metadata</th>
            <th>вход</th>
            <th>выход</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((l) => (
            <tr key={l.id}>
              <td className="muted">{new Date(l.ts).toLocaleString()}</td>
              <td>{l.module}</td>
              <td>{l.duration_ms}</td>
              <td><MetaCell meta={l.meta} onPick={(k, v) => { setMetaKey(k); setMetaValue(v); }} /></td>
              <td>{l.input}</td>
              <td className="mono">{l.output}</td>
            </tr>
          ))}
          {logs.length === 0 && <tr><td colSpan={6} className="muted">логов нет</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

// Показывает пары key=value чипсами; клик по чипу подставляет их в фильтр.
function MetaCell({ meta, onPick }) {
  if (!meta || Object.keys(meta).length === 0) return <span className="muted">—</span>;
  return (
    <div className="words">
      {Object.entries(meta).map(([k, v]) => (
        <span className="word-chip" key={k} style={{ cursor: "pointer" }}
              title="фильтровать по этому значению"
              onClick={() => onPick(k, String(v))}>
          {k}={String(v)}
        </span>
      ))}
    </div>
  );
}
