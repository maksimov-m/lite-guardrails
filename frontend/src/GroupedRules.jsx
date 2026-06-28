import React, { useEffect, useState } from "react";
import * as api from "./api.js";

// Универсальный список правил, сгруппированный по label (тег/категория).
// Используется для PII (несколько regex на тег) и relevant (фразы по категориям).
export default function GroupedRules({ module, valueLabel, labelName, onError }) {
  const [rules, setRules] = useState([]);
  const [newLabel, setNewLabel] = useState("");
  const [newValue, setNewValue] = useState("");

  const load = async () => {
    try { setRules((await api.listRules(module)).rules); }
    catch (e) { onError(e.message); }
  };
  useEffect(() => { load(); }, [module]);

  const toggle = async (r) => {
    try { await api.patchRule(r.id, { enabled: !r.enabled }); load(); }
    catch (e) { onError(e.message); }
  };
  const remove = async (r) => {
    try { await api.deleteRule(r.id); load(); }
    catch (e) { onError(e.message); }
  };
  const add = async () => {
    if (!newValue.trim() || !newLabel.trim()) return;
    try {
      await api.createRule({ module, label: newLabel, value: newValue });
      setNewValue(""); load(); onError("");
    } catch (e) { onError(e.message); }
  };

  const groups = {};
  for (const r of rules) (groups[r.label] = groups[r.label] || []).push(r);
  const labels = Object.keys(groups).sort();

  return (
    <div>
      <div className="card">
        <div className="row">
          <input list="labels" placeholder={labelName} value={newLabel}
                 onChange={(e) => setNewLabel(e.target.value)} style={{ maxWidth: 220 }} />
          <datalist id="labels">{labels.map((l) => <option key={l} value={l} />)}</datalist>
          <input placeholder={`новое: ${valueLabel}`} value={newValue}
                 onChange={(e) => setNewValue(e.target.value)} style={{ flex: 1 }}
                 onKeyDown={(e) => e.key === "Enter" && add()} />
          <button className="primary" onClick={add}>+ Добавить</button>
        </div>
      </div>

      {labels.map((label) => (
        <div className="card" key={label}>
          <div className="group-h">{label} <span className="muted">· {groups[label].length}</span></div>
          {groups[label].map((r) => (
            <div className="rule-row" key={r.id}>
              <input type="checkbox" checked={r.enabled} onChange={() => toggle(r)} />
              <span className="mono rule-val">{r.value}</span>
              <button className="danger" title="удалить" onClick={() => remove(r)}>✕</button>
            </div>
          ))}
        </div>
      ))}
      {labels.length === 0 && <p className="muted">правил нет</p>}
    </div>
  );
}
