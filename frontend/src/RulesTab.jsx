import React, { useState } from "react";
import PiiRules from "./PiiRules.jsx";
import DictionaryManager from "./DictionaryManager.jsx";
import { nsfwResource, relevantResource } from "./resources.js";

const MODULES = [
  { key: "pii", label: "PII" },
  { key: "nsfw", label: "NSFW" },
  { key: "relevant", label: "Relevant" },
];

export default function RulesTab({ onError }) {
  const [module, setModule] = useState("pii");

  return (
    <div>
      <div className="row" style={{ marginBottom: 16 }}>
        <div className="segment">
          {MODULES.map((m) => (
            <button key={m.key} className={m.key === module ? "active" : ""}
                    onClick={() => { setModule(m.key); onError(""); }}>
              {m.label}
            </button>
          ))}
        </div>
        <span className="muted">изменения применяются сразу</span>
      </div>

      {module === "pii" && <PiiRules onError={onError} />}
      {module === "nsfw" && <DictionaryManager resource={nsfwResource} onError={onError} />}
      {module === "relevant" && <DictionaryManager resource={relevantResource} onError={onError} />}
    </div>
  );
}
