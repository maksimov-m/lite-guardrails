// Тонкая обёртка над API гуарда.
// Хранит в localStorage: базовый URL, admin-токен (для /admin/*) и клиентский
// API-ключ (для /detect, /anonymize, /deanonymize). Настраивается в UI.

export function getConfig() {
  return {
    // Базовый URL API задаётся на сборке из .env (VITE_API_BASE). Пусто =
    // относительный путь (тот же origin: nginx-прокся в контейнере / vite в dev).
    base: import.meta.env.VITE_API_BASE || "",
    token: localStorage.getItem("gr_token") || "admin",
    apiKey: localStorage.getItem("gr_apikey") || "",
  };
}

export function setConfig({ token, apiKey }) {
  if (token !== undefined) localStorage.setItem("gr_token", token);
  if (apiKey !== undefined) localStorage.setItem("gr_apikey", apiKey);
}

async function request(method, path, { body, admin, apiKey } = {}) {
  const cfg = getConfig();
  const headers = { "Content-Type": "application/json" };
  if (admin) headers["X-Admin-Token"] = cfg.token;
  if (apiKey) headers["X-API-Key"] = cfg.apiKey;

  const res = await fetch(cfg.base + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : res.statusText;
    throw new Error(`${res.status}: ${detail}`);
  }
  return data;
}

// --- детекция / демо (требуют клиентский X-API-Key) ---
export const detect = (module, text, metadata) =>
  request("POST", `/detect/${module}`, {
    body: metadata ? { text, metadata } : { text },
    apiKey: true,
  });
export const anonymize = (text) =>
  request("POST", "/anonymize", { body: { text }, apiKey: true });
export const deanonymize = (id, text) =>
  request("POST", "/deanonymize", { body: { id, text }, apiKey: true });

// --- админ: PII (regex-сигнатуры по типам) ---
export const listPii = () => request("GET", "/admin/pii", { admin: true });
export const createPii = (rule) =>
  request("POST", "/admin/pii", { body: rule, admin: true });
export const patchPii = (id, patch) =>
  request("PATCH", `/admin/pii/${id}`, { body: patch, admin: true });
export const deletePii = (id) =>
  request("DELETE", `/admin/pii/${id}`, { admin: true });

// --- админ: NSFW-словари (имя + text со словами через пробел) ---
export const listDicts = () => request("GET", "/admin/nsfw", { admin: true });
export const getDict = (id) => request("GET", `/admin/nsfw/${id}`, { admin: true });
export const createDict = (name, text = "") =>
  request("POST", "/admin/nsfw", { body: { name, text }, admin: true });
export const patchDict = (id, patch) =>
  request("PATCH", `/admin/nsfw/${id}`, { body: patch, admin: true });
export const deleteDict = (id) =>
  request("DELETE", `/admin/nsfw/${id}`, { admin: true });

// --- админ: Relevant-категории (тип + text с фразами по строкам) ---
export const listCats = () => request("GET", "/admin/relevant", { admin: true });
export const createCat = (type, text = "") =>
  request("POST", "/admin/relevant", { body: { type, text }, admin: true });
export const patchCat = (id, patch) =>
  request("PATCH", `/admin/relevant/${id}`, { body: patch, admin: true });
export const deleteCat = (id) =>
  request("DELETE", `/admin/relevant/${id}`, { admin: true });

// --- админ: API-ключи клиентов ---
export const listKeys = () => request("GET", "/admin/api-keys", { admin: true });
export const createKey = (name) =>
  request("POST", "/admin/api-keys", { body: { name }, admin: true });
export const patchKey = (id, patch) =>
  request("PATCH", `/admin/api-keys/${id}`, { body: patch, admin: true });
export const deleteKey = (id) =>
  request("DELETE", `/admin/api-keys/${id}`, { admin: true });

// --- админ: версия конфига (используется как проверка admin-токена при логине) ---
export const getVersion = () => request("GET", "/admin/version", { admin: true });

// --- админ: логи прогонов ---
export const getLogs = (module, limit = 100, metaKey, metaValue) => {
  let path = `/admin/logs?limit=${limit}`;
  if (module) path += `&module=${module}`;
  if (metaKey) path += `&meta_key=${encodeURIComponent(metaKey)}`;
  if (metaValue) path += `&meta_value=${encodeURIComponent(metaValue)}`;
  return request("GET", path, { admin: true });
};
export const getMetaKeys = () =>
  request("GET", "/admin/logs/meta-keys", { admin: true });

// Скачивание NSFW-словаря .txt: тянем blob с admin-токеном и кликаем по ссылке.
export async function downloadDict(id, name) {
  const cfg = getConfig();
  const res = await fetch(`${cfg.base}/admin/nsfw/${id}/export`, {
    headers: { "X-Admin-Token": cfg.token },
  });
  if (!res.ok) throw new Error(`${res.status}: не удалось скачать`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(name || "dict").replace(/[^\w.-]+/g, "_")}.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
