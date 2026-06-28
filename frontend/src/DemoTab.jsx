import React, { useState } from "react";
import * as api from "./api.js";

export default function DemoTab({ onError }) {
  const [text, setText] = useState("Привет! Мой email a@b.com и тел 89991330855");
  const [metaStr, setMetaStr] = useState('{"user_id": "42", "app": "support-bot"}');
  const [result, setResult] = useState(null);

  // состояние анонимизации
  const [anonText, setAnonText] = useState("пиши на a@b.com и a@b.com, тел 89991330855");
  const [anonOut, setAnonOut] = useState(null);
  const [deanonId, setDeanonId] = useState("");
  const [deanonText, setDeanonText] = useState("");
  const [deanonOut, setDeanonOut] = useState(null);

  const run = async (module) => {
    let metadata = null;
    if (metaStr.trim()) {
      try { metadata = JSON.parse(metaStr); }
      catch { onError("metadata: невалидный JSON"); return; }
    }
    try { setResult(await api.detect(module, text, metadata)); onError(""); }
    catch (e) { onError(e.message); }
  };
  const doAnon = async () => {
    try {
      const r = await api.anonymize(anonText);
      setAnonOut(r); setDeanonId(r.id); setDeanonText(r.text); onError("");
    } catch (e) { onError(e.message); }
  };
  const doDeanon = async () => {
    try { setDeanonOut(await api.deanonymize(deanonId, deanonText)); onError(""); }
    catch (e) { onError(e.message); }
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Детекторы</h3>
        <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} />
        <label className="muted" style={{ display: "block", margin: "8px 0 4px" }}>
          metadata (JSON, опционально — попадёт в логи)
        </label>
        <textarea rows={2} className="mono" value={metaStr}
                  onChange={(e) => setMetaStr(e.target.value)} />
        <div className="row" style={{ marginTop: 8 }}>
          <button onClick={() => run("pii")}>PII</button>
          <button onClick={() => run("nsfw")}>NSFW</button>
          <button onClick={() => run("relevant")}>Relevant</button>
        </div>
        {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Анонимизация (PII → теги)</h3>
        <textarea rows={2} value={anonText} onChange={(e) => setAnonText(e.target.value)} />
        <div className="row" style={{ marginTop: 8 }}>
          <button className="primary" onClick={doAnon}>Анонимизировать</button>
        </div>
        {anonOut && <pre>{JSON.stringify(anonOut, null, 2)}</pre>}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Деанонимизация (теги → оригинал)</h3>
        <div className="row">
          <input placeholder="id" value={deanonId} onChange={(e) => setDeanonId(e.target.value)} style={{ maxWidth: 320 }} />
        </div>
        <textarea rows={2} style={{ marginTop: 8 }} value={deanonText} onChange={(e) => setDeanonText(e.target.value)} />
        <div className="row" style={{ marginTop: 8 }}>
          <button className="primary" onClick={doDeanon}>Деанонимизировать</button>
        </div>
        {deanonOut && <pre>{JSON.stringify(deanonOut, null, 2)}</pre>}
      </div>
    </div>
  );
}
