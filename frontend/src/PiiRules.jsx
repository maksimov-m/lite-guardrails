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
  const saveRegex = async (r, newRegex) => {
    try { await api.patchPii(r.id, { regex: newRegex }); load(); onError(""); return true; }
    catch (e) { onError(e.message); return false; } // 400 с бэка = невалидный regex
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
            <RuleRow key={r.id} rule={r} onToggle={toggle} onSave={saveRegex} onRemove={remove} />
          ))}
        </div>
      ))}
      {types.length === 0 && <p className="muted">правил нет</p>}
    </div>
  );
}

// Строка правила с инлайн-редактированием regex: карандаш -> поле ввода,
// Enter/«Сохранить» шлёт PATCH (невалидный regex отклонит бэкенд), Esc — отмена.
function RuleRow({ rule, onToggle, onSave, onRemove }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(rule.regex);

  const startEdit = () => { setDraft(rule.regex); setEditing(true); };
  const save = async () => {
    if (draft.trim() === rule.regex) { setEditing(false); return; }
    if (await onSave(rule, draft.trim())) setEditing(false);
  };

  if (editing) {
    return (
      <div className="rule-row">
        <input type="checkbox" checked={rule.enabled} disabled />
        <input className="mono" value={draft} autoFocus style={{ flex: 1 }}
               onChange={(e) => setDraft(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === "Enter") save();
                 if (e.key === "Escape") setEditing(false);
               }} />
        <button className="primary" onClick={save}>Сохранить</button>
        <button className="ghost" onClick={() => setEditing(false)}>Отмена</button>
      </div>
    );
  }
  return (
    <div className="rule-row">
      <input type="checkbox" checked={rule.enabled} onChange={() => onToggle(rule)} />
      <span className="mono rule-val">{rule.regex}</span>
      <button className="ghost" title="редактировать regex" onClick={startEdit}>✎</button>
      <button className="danger" title="удалить" onClick={() => onRemove(rule)}>✕</button>
    </div>
  );
}
