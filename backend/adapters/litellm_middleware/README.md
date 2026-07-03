# lite-guardrails ↔ LiteLLM

Кастомный guardrail для [LiteLLM Proxy](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail),
который делегирует проверки нашему HTTP-сервису `lite-guardrails`. Гуард остаётся
отдельным сервисом со своей админкой и БД — middleware только ходит к нему по сети,
поэтому правила/словари меняются в админке и подхватываются на лету.

## Что делает

На каждый запрос через прокси:

| Этап | Хук | Что проверяет |
|------|-----|----------------|
| Вход | `async_pre_call_hook` | промпт пользователя: relevant → nsfw → pii |
| Выход | `async_post_call_success_hook` | ответ модели: деанонимизация PII, nsfw |

Действие по **каждому модулю** настраивается независимо:

| Параметр | Значения | По умолчанию |
|----------|----------|--------------|
| `pii_action` | `anonymize` · `block` · `log` · `off` | `anonymize` |
| `nsfw_action` | `block` · `log` · `off` | `block` |
| `relevant_action` | `block` · `log` · `off` | `block` |

- **anonymize** — PII заменяется на теги (`<EMAIL_1>`…) через `/anonymize` перед
  отправкой в LLM; в ответе теги возвращаются обратно через `/deanonymize`.
  Реальные данные в LLM не уходят, пользователь видит оригинал.
- **block** — при срабатывании запрос/ответ отклоняется (HTTP 400).
- **log** — пропускаем, но прогон фиксируется в логах гуарда.
- **off** — модуль не используется.

Каждый вызов к гуарду помечается metadata `{"source":"litellm","stage":"input|output","model":...,"user_id":...}`
— в админке на вкладке «Логи» можно фильтровать по `source=litellm`.

## Подключение

1. Установить зависимости в окружение прокси:
   ```bash
   pip install -r requirements.txt
   ```

2. Положить `lite_guardrails.py` туда, где его найдёт прокси (рядом с
   `config.yaml`), и добавить каталог в `PYTHONPATH`:
   ```bash
   export PYTHONPATH="$PWD:$PYTHONPATH"
   ```

3. Указать guardrail в `config.yaml` (см. `config.example.yaml`):
   ```yaml
   guardrails:
     - guardrail_name: "lite-guardrails"
       litellm_params:
         guardrail: lite_guardrails.LiteGuardrails
         mode: "pre_call"
         default_on: true
         guard_base_url: "http://localhost:8000"
         pii_action: "anonymize"
         nsfw_action: "block"
         relevant_action: "block"
   ```

4. Запустить прокси:
   ```bash
   litellm --config config.yaml
   ```

## Как пользователю включить/выключить гуард

- **Нужен только наш API без гуарда** — просто обращайтесь напрямую к сервису
  `lite-guardrails` (`/v1/detect/*`, `/v1/anonymize`), прокси не используется.
- **Гуард на всех запросах** — `default_on: true` (как выше).
- **Гуард опционально, по запросу** — `default_on: false`, и клиент включает его
  per-request:
  ```bash
  curl http://localhost:4000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
      "model": "gpt-4o-mini",
      "messages": [{"role":"user","content":"мой email a@b.com"}],
      "guardrails": ["lite-guardrails"]
    }'
  ```
- **Отдельные политики** — заведите несколько guardrail-блоков с разными
  `guardrail_name` и действиями (например `pii-strict` с `pii_action: block`
  и `pii-soft` с `pii_action: anonymize`) и выбирайте нужный в поле `guardrails`.

## Конфиг через переменные окружения

Если параметр не задан в `config.yaml`, берётся из env, иначе — дефолт:

| env | дефолт |
|-----|--------|
| `GUARD_BASE_URL` | `http://localhost:8000` |
| `GUARD_PII_ACTION` | `anonymize` |
| `GUARD_NSFW_ACTION` | `block` |
| `GUARD_RELEVANT_ACTION` | `block` |
| `GUARD_CHECK_INPUT` | `true` |
| `GUARD_CHECK_OUTPUT` | `true` |
| `GUARD_FAIL_CLOSED` | `false` (гуард недоступен → запрос пропускается) |
| `GUARD_API_KEY` | `""` (ключ для детекшн-ручек, заголовок `X-API-Key`; выдаётся в админке) |

## Замечания

- При `pii_action: anonymize` анонимизируются все строковые сообщения одним
  вызовом (сквозная нумерация тегов), а на выходе теги восстанавливаются по
  сохранённому id маппинга (хранится в Redis с TTL — см. `MAPPING_TTL_SECONDS`).
  Если TTL истёк до ответа модели, текст возвращается с тегами как есть.
- `relevant` и `nsfw` во входе проверяются по последнему сообщению пользователя.
- `fail_closed: false` (дефолт) — если сервис гуарда лёг, прокси не падает, а
  пропускает запрос (с warning в лог). Для строгого режима поставьте `true`.
