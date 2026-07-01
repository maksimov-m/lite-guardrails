import React, { useEffect, useState } from "react";
import * as api from "./api.js";

// PII-правила — regex-сигнатуры, сгруппированные по типу (EMAIL, PHONE…).
// На один тип может быть несколько regex.
export default function PiiRules({ onError }) {
  const [rules, setRules] = useState([]);
  const [type, setType] = useState("");
  const [regex, setRegex] = useState("");

  const load = async () => {
    try { setRules((await api.listPii()).rules); onError(""); }
    catch (e) { onError(e.message); }
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!type.trim() || !regex.trim()) return;
    try {
      await api.createPii({ type: type.trim(), regex: regex.trim(), enabled: true });
      setRegex(""); load();
    } catch (e) { onError(e.message); }
  };
  const toggle = async (r) => {
    try { await api.patchPii(r.id, { enabled: !r.enabled }); load(); }
    catch (e) { onError(e.message); }
  };
  const remove = async (r) => {
    try { await api.deletePii(r.id); load(); }
    catch (e) { onError(e.message); }
  };

  const groups = {};
  for (const r of rules) (groups[r.type] = groups[r.type] || []).push(r);
  const types = Object.keys(groups).sort();

  return (
    <div>
      <div className="card">
        <div className="row">
          <input list="pii-types" placeholder="тег (EMAIL, PHONE…)" value={type}
                 onChange={(e) => setType(e.target.value)} style={{ maxWidth: 220 }} />
          <datalist id="pii-types">{types.map((t) => <option key={t} value={t} />)}</datalist>
          <input placeholder="regex" className="mono" value={regex}
                 onChange={(e) => setRegex(e.target.value)} style={{ flex: 1 }}
                 onKeyDown={(e) => e.key === "Enter" && add()} />
          <button className="primary" onClick={add}>+ Добавить</button>
        </div>
      </div>

      {types.map((t) => (
        <div className="card" key={t}>
          <div className="group-h">{t} <span className="muted">· {groups[t].length}</span></div>
          {groups[t].map((r) => (
            <div className="rule-row" key={r.id}>
              <input type="checkbox" checked={r.enabled} onChange={() => toggle(r)} />
              <span className="mono rule-val">{r.regex}</span>
              <button className="danger" title="удалить" onClick={() => remove(r)}>✕</button>
            </div>
          ))}
        </div>
      ))}
      {types.length === 0 && <p className="muted">правил нет</p>}
    </div>
  );
}
