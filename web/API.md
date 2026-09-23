# API нового экрана — контракт (Claude, 23.09 17:00)

Сервер: `server.py` (пишет Claude). Для проверки экрана — http://localhost:8767 (полный API).
Все ответы — JSON движка `akim` как есть. Ошибка → HTTP 400 `{"error": "текст для человека"}`.
Набор `plan` — ровно 5 элементов `{"measure": "M7", "district": "Нура"}`; у городских мер `"district": null`.
Тексты для человека (сообщения ошибок, разбор, ответы агента, шаги, предупреждения) сервер уже переводит
в простые слова: без «Score», без кодов M7, числа с запятой. Экран выводит их как есть, чисел не придумывает.

## Чтение
- `GET /api/health` → `{"ok": true}`
- `GET /api/initial` → `{data, base, plan, result, best, events, total, model}`
  - `events`: `[{id, name, description}]` — 4 городских события; `total`: 694395; `model`: true, если есть ключ OpenAI.
- `GET /api/top` → 5 лучших: `[{score, cost, rank, weakest_district: {name, d}, plan}]`
- `GET /api/frontier` → `[{cost, score}]` — лучший индекс при каждой сумме затрат
- `GET /api/approved` → `[{approved_at, score, budget_used}]` — история утверждений
- `GET /api/leaderboard` → `[{place, team, score, delta, rank, budget_used, weakest: {name}}]`

## Расчёт (POST, тело JSON)
- `/api/evaluate` `{plan}` → `{valid, errors: [{message}], score, base_score, delta, budget_used, budget, n_crit,
  critical, resolved_critical, new_critical, min_district: {name, d}, districts: [{name, d_before, d_after,
  values_before, values_after}], contributions: [{name, district, score_contribution}], synergies}`
- `/api/rank` `{plan}` → `{rank, total, best_score}`
- `/api/district` `{plan, district}` → `{d, place_from_bottom, profile, weak: [{name, value}],
  best_measures: [{name, cost, d_gain, score_gain}]}`

## ИИ-агент
- `/api/explain` `{plan}` → `{mode: "llm"|"template", note?, strengths: [], risks: [], consequences: [], text}`
  — «Разбор написал ИИ по расчётам, каждое число сверено» при `llm`, иначе «составлен программой по расчётам».
- `/api/improve` `{plan}` → `{better, current_score, best: {replace: {measure, district}, with: {measure, district},
  replace_name, with_name, plan, score, delta}}` — кнопка «Применить» ставит `best.plan`.
- `/api/mission` `{plan, text}` → `{status: "ok"|"infeasible", constraints: [], steps: [{role, action, result}],
  recommendation: {score, cost, plan, words}, price, warnings: [], suggestion, text}` — «Применить» ставит `suggestion`.
  Текст по умолчанию: «Улучши, но не ухудшай качество воздуха в Сарыарке».
- `/api/chat` `{plan, message, history: [{role, content}]}` → `{reply, mode, tools_used: [], suggestion, mission?, note?}`
  — кнопка «Применить предложение» только пока набор не менялся с момента вопроса.
- `/api/transcribe` — тело: байты аудио (wav/webm), заголовок `Content-Type: audio/*` → `{text}`; без ключа — 400 с пояснением.

## Проверка на прочность
- `/api/stress` `{plan, event_id}` → `{event: {id, name}, score_before, score_after, delta, new_critical: [{district,
  name, value}], advice: {replace, with, replace_name, with_name, plan, score, delta} | null}`
- `/api/robust` `{plan}` → `{events: [имена], yours | null, best, robust: {..., rank}, same, price, gain,
  top_gain: {event, diff}}`; строка набора: `{plan, words, score, by_event: [{event, score, n_crit}], worst,
  worst_event, loss, max_crit}`. Считает около 6 с — показать «Проверяем все 694 395 наборов…».
- `/api/sensitivity` `{plan}` → `[{direction, name, score, best_score, gap}]` — около 8 с.
- `/api/find` `{max_budget, include: [], exclude: [], min_district_d}` → как `/api/top`, до 5 вариантов.
- `/api/compare` `{plan_a, plan_b}` → `{a: {score}, b: {score}, score_diff, districts: [{name, d_a, d_b, diff}],
  only_in_a_words, only_in_b_words}` — сравнение сохранённого варианта A с текущим набором.

## Решение человека
- `/api/approve` `{plan}` → `{approved_at, score, budget_used}`; недопустимый набор → 400.
- `/api/brief` `{plan}` → `{filename, markdown}` — паспорт сценария, скачать файлом на стороне экрана.
- `/api/submit` `{team, plan}` → `{ok: true}`; пустое название или недопустимый набор → 400.
