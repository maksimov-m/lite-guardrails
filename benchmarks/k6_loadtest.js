// Нагрузочное тестирование guard через k6 (нативный многопоточный генератор).
//
// Запуск внутри docker-сети, чтобы бить прямо в контейнер по имени сервиса и
// обойти и python-GIL, и windows-проксирование портов Docker Desktop:
//
//   docker run --rm -i --network lite_guardrails_default \
//     -e MODULE=pii -e MAX_VUS=400 grafana/k6 run - < benchmarks/k6_loadtest.js
//
// Параметры через env: BASE, MODULE (pii|nsfw|relevant), MAX_VUS.

import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE || 'http://guardrails:8000';
const MODULE = __ENV.MODULE || 'pii';
const MAX_VUS = parseInt(__ENV.MAX_VUS || '400');

const SAMPLES = {
  pii: 'Привет! Мой email maks@gmail.com и телефон 89991330855, сайт https://example.com/path',
  nsfw: 'совершенно обычное приличное предложение про погоду и природу вокруг',
  relevant: 'Расскажи, как устроен механизм газораспределения в двигателе автомобиля',
};

const payload = JSON.stringify({ text: SAMPLES[MODULE] });
const params = { headers: { 'Content-Type': 'application/json' } };

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: Math.round(MAX_VUS * 0.25) },
        { duration: '20s', target: Math.round(MAX_VUS * 0.5) },
        { duration: '20s', target: MAX_VUS },
        { duration: '20s', target: MAX_VUS },
        { duration: '10s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],      // <1% ошибок
    http_req_duration: ['p(95)<200'],    // p95 < 200 ms
  },
};

export default function () {
  const res = http.post(`${BASE}/detect/${MODULE}`, payload, params);
  check(res, { 'status 200': (r) => r.status === 200 });
}
