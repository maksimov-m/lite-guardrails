import React, { useEffect, useState } from "react";
import * as api from "./api.js";

// PII-правила — regex-сигнатуры, сгруппированные по типу (EMAIL, PHONE…).
// На один тип может быть несколько regex.
const PAGE = 50;

export default function PiiRules({ onError }) {
  const [rules, setRules] = useState([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [type, setType] = useState("");
  const [regex, setRegex] = useState("");

  const load = async (offset) => {
    try {
      const r = await api.listPii(PAGE, offset);
      setRules(r.rules);
      setHasMore(r.has_more);
      onError("");
    } catch (e) { onError(e.message); }
  };
  useEffect(() => { load(page * PAGE); }, [page]);

  const add = async () => {
    if (!type.trim() || !regex.trim()) return;
    try {
      await api.createPii({ type: type.trim(), regex: regex.trim(), enabled: true });
      setRegex("");
      page === 0 ? load(0) : setPage(0);
    } catch (e) { onError(e.message); }
  };
  const reload = () => load(page * PAGE);
  const toggle = async (r) => {
    try { await api.patchPii(r.id, { enabled: !r.enabled }); reload(); }
    catch (e) { onError(e.message); }
  };
  const saveRegex = async (r, newRegex) => {
    try { await api.patchPii(r.id, { regex: newRegex }); reload(); onError(""); return true; }
    catch (e) { onError(e.message); return false; } // 400 с бэка = невалидный regex
  };
  const remove = async (r) => {
    try { await api.deletePii(r.id); reload(); }
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
      {types.length === 0 && (
        <p className="muted">Правил пока нет. Задайте тег и regex выше, чтобы добавить первое.</p>
      )}

      {(hasMore || page > 0) && (
        <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
          <button className="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            ← Назад
          </button>
          <span className="muted">стр. {page + 1}</span>
          <button className="ghost" disabled={!hasMore} onClick={() => setPage((p) => p + 1)}>
            Вперёд →
          </button>
        </div>
      )}
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
