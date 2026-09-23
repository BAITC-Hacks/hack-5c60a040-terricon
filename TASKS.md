# TASKS.md — очередь заданий дня

Кейс «Аким на 5 часов», трек «03 · Управление». Схема и план по часам: https://claude.ai/artifact/LnHERDbzHZWnkqebJmxNXb
Перед каждым заданием: «Прочитай CASE.md и TASKS.md. Выполни задачу N».
Цифры — только из `docs/task/akim_dataset.md` и таблицы «Проверено кодом» в `CASE.md`.

**Архитектура (решение команды 23.09, 13:35): одна программа на Streamlit.** Запуск:
`pip install -r requirements.txt` → `streamlit run app.py`. Экран `app.py` вызывает функции движка `akim/`
(обычный Python-импорт, без отдельного сервера). Экран ничего не считает: всё, что на нём видно, — поля ответа движка.

**Агентная система (решение Виталия 13:50): 4 роли, 12 инструментов, 2 проверки, человек.**
Проверка на входе → координатор (с ключом — модель с вызовом инструментов, до 5 шагов; без ключа — правила) →
инструменты: Аналитик (проверка правил, расчёт, разбор компромиссов, паспорт района, сравнение), Стратег
(улучшить на одну меру, подбор под цель по всем 694 395 наборам, кривая «бюджет → Score»), Риск-менеджер
(«что если», городские события, устойчивость к приоритетам), Докладчик (паспорт сценария, карта районов) →
проверка чисел на выходе → человек: «Применить» и «Утвердить» только кнопкой, у агента инструмента утверждения нет.
Мультимодальность: голосовое поручение (распознавание речи, с ключом), карта районов, скачиваемый паспорт.

**Зоны.** Виталий + Codex: `app.py`, `tests/test_app.py`. Движок (`akim/`, `data/`, остальные `tests/`,
`scripts/`, `requirements.txt`, Docker) — Дмитрий: до 14:20 его писал Claude с ноутбука Виталия, дальше ведёт
Дмитрий со своим Codex, Claude в `akim/` не пишет. `CASE.md`, `TASKS.md`, README — Claude. Codex Виталия не коммитит:
коммитит и отправляет Claude после проверки.

Статусы: ⬜ ждёт · 🔨 в работе · 🔍 на проверке · ✅ принята · ↩ откат

| Движок | Экран |
| --- | --- |
| Д-1 данные, правила, формула, перебор, тесты — ✅ Claude | В-1 сборка 5 решений — ✅ Codex |
| Д-2 разбор компромиссов со сверкой чисел — ✅ Claude | В-2 экран результата — ✅ Codex |
| Д-3 координатор агента и цикл поручения — ✅ Claude | В-3 разбор, поручение агенту с журналом шагов, чат, голос — ✅ Codex |
| Д-4 «Утвердить» и история — ✅ Claude | В-4 сравнение, топ-5, «Утвердить» — 🔨 Codex |
| Д-5 Docker и запуск без Docker — ✅ Claude (сборка не проверена → Д-9) | В-5 подбор под цель, карта, паспорта, события |
| Д-6 городские события и устойчивость — ✅ Claude | В-6 рейтинг команд (после Д-10) |
| Д-7 инструменты Аналитика и Стратега, паспорт сценария, голос — ✅ Claude | |
| Д-8 главный сценарий одной командой — ⬜ Дмитрий, до 14:40 | |
| Д-9 чистый клон на ноутбуке Дмитрия, оба способа запуска — ⬜ Дмитрий, до 15:15 | |
| Д-10 рейтинг команд — ⬜ Дмитрий, до 15:50 | |

## Контракт движка — экран вызывает только это

```python
import akim

akim.load_data()   # dict: budget (100); districts [{name, population_share, profile, values{T1..C2}}];
                   # indicators [{code, direction, name, weight, meaning}];
                   # measures [{id, direction, name, scope: "district"|"city", cost, lag, effects{код: +N}}];
                   # directions [{code, name}]; synergies [{pair, indicator, bonus}];
                   # conflicts [{pair, same_district_only, reason}]

akim.baseline()    # {score, d_avg, n_crit, critical[{district, indicator, value}],
                   #  districts[{name, population_share, d, values{}}]}

plan = [{"measure": "M7", "district": "Нура"}, {"measure": "M12", "district": None}, ...]   # 5 решений

akim.evaluate(plan)
# {valid, errors[{code, message, measures}],
#  plan[{measure, district, name, direction, scope, cost, lag, realized_share}],
#  budget, budget_used, budget_left,
#  score, base_score, delta, d_avg, base_d_avg, min_district{name, d}, n_crit,
#  critical[{district, indicator, value}], resolved_critical[...], new_critical[...],
#  districts[{name, population_share, d_before, d_after, d_delta, values_before{}, values_after{}}],
#  contributions[{measure, district, name, cost, score_contribution}],
#  synergies[{pair, district, indicator, bonus}], directions{code: count}}
# Недопустимый набор: valid=False, errors с причинами, бюджетные поля заполнены,
# score/delta/d_avg/min_district/n_crit = None, списки пустые, values_after/d_after = None.

akim.explain(plan)        # {mode: "llm"|"template", strengths[], risks[], consequences[], text, suggestion, note?}
akim.improve(plan)        # {better, current_score, best{replace, with, score, delta, plan} | None, alternatives[...]}
akim.top(5)               # [{score, cost, plan}] — лучшие из 694 395 допустимых наборов
akim.find_best(max_budget=100, include=(), exclude=(), min_district_d=None, n=5)   # [{score, cost, plan}]
akim.frontier()           # [{cost, score, plan}] — лучший Score при каждой сумме затрат
akim.district_report(district, plan=None)
                          # {district, profile, d, weak[{indicator, name, value}],
                          #  best_measures[{measure, name, cost, d_gain, score_gain}]}
akim.compare(plan_a, plan_b)   # {a, b (ответы evaluate), score_diff, districts[{name, d_a, d_b, diff}], only_in_a[], only_in_b[]}
akim.what_if(plan, remove=None, add=None)   # {before, after (ответ evaluate), delta, new_plan}
akim.events()             # [{id, name, description, shocks[{district, indicator, change}]}]
akim.stress_test(plan, event_id)   # {event, score_before, score_after, delta, new_critical[], advice}
akim.sensitivity(plan)    # [{direction, name, score, best_score, best_plan}] — если вес направления выше на 20%
akim.brief(plan)          # str, Markdown — паспорт сценария для акима
akim.transcribe(audio_bytes)   # str; без ключа — RuntimeError с понятным текстом
akim.chat(message, plan, history)   # {reply, mode: "llm"|"rules", intent, tools_used[], suggestion: plan | None,
                          #  note?, mission? — если агент выполнял поручение, там журнал шагов (как у run_mission)}
akim.parse_request(text, plan)      # поручение текстом → условия: {max_budget, keep[{measure, district}], exclude[],
                          #  protect[{district, indicator}], min_district_d, maximize}
akim.run_mission(plan, request)     # {status: "ok"|"infeasible", constraints[] (словами), steps[{role, action, result}],
                          #  recommendation{score, cost, rank, weakest_district, district_d, plan} | None, alternative,
                          #  free_best, price (цена условий в баллах), warnings[] (что ухудшится), suggestion, text, retried}
akim.search_plans(...)    # как find_best, плюс min_indicators[{district, indicator, min}]; {plans, matched, total, complete}
akim.approve(plan)        # {approved_at, score, delta, budget_used, plan, note}; недопустимый — ValueError с причиной
akim.approved()           # [{approved_at, score, delta, budget_used, plan, note}]
akim.submit(team, plan)   # Д-10: {team, submitted_at, score, delta, rank, total, budget_used, weakest{name, d}, plan};
                          #  пустое имя или недопустимый набор — ValueError с причиной; та же команда ещё раз — замена
akim.leaderboard()        # Д-10: [{place, team, score, delta, rank, budget_used, weakest{name, d}, submitted_at}],
                          #  по убыванию score
```

Эталон для тестов: база 52.56 (Нура 49.18, ниже 40 — S1 и S2 в Нуре); пример организаторов
M7 Нура, M8 Нура, M10 Нура, M12, M5 Сарыарка → 56.54, бюджет 95, дельта +3.98, Нура 52.96;
«Улучшить» на примере: заменить M5 Сарыарка на M3 Нура → 57.21 (+0.67), это 3-й лучший набор;
лучший набор 57.24 (M2, M3 Нура, M8 Нура, M9 Нура, M14; стоимость 98).

---

## Д-1. Данные, правила, формула, перебор — ✅ Claude

ЦЕЛЬ: движок считает Score строго по формуле ТЗ и отказывает недопустимому набору с причиной.
ГДЕ: `data/akim.json`, `akim/data.py`, `akim/rules.py`, `akim/scoring.py`, `akim/optimizer.py`,
`scripts/precompute.py`, `data/top_plans.json`, `tests/test_scoring.py`, `tests/test_rules.py`, `tests/test_optimizer.py`.
НЕЛЬЗЯ: модель в расчёте; числа, которых нет в датасете.
ГОТОВО: `python -m pytest -q` зелёный; база 52.56, пример 56.54, дешёвый набор 61 допустим, топ-1 57.24,
всего 694 395; отказ по каждому из правил с причиной на русском.

## Д-2. Разбор компромиссов — ✅ Claude

ГДЕ: `akim/explainer.py`, `akim/llm.py`, `tests/test_explainer.py`.
НЕЛЬЗЯ: модель считает или придумывает числа; `temperature` в вызове модели; ключ в коде.
ГОТОВО: без `OPENAI_API_KEY` — шаблон из чисел расчёта (`mode: "template"`); с ключом — текст модели
(`mode: "llm"`), каждое число в нём сверено с расчётом, не сошлось или ошибка — шаблон с пометкой `note`.

## Д-3. Координатор агента — ✅ Claude

ЦЕЛЬ: агент сам выбирает инструменты движка под запрос и объясняет результат.
ГДЕ: `akim/agent.py`, `tests/test_agent.py`.
НЕЛЬЗЯ: менять набор пользователя без его нажатия; инструмент «утвердить» у агента; отвечать про реальных людей и политику.
ГОТОВО: проверка на входе до модели («поставь Score 100», «забудь правила», реальные акимы и политика — вежливый
отказ «это симулятор на условных данных»); с ключом — модель с инструментами (evaluate, explain, improve,
find_best, frontier, district_report, compare, what_if, stress_test, sensitivity), до 5 шагов, `reasoning_effort="none"`,
без `temperature`; без ключа — правила по смыслу: «улучши», «почему», «что если M3 в Нуре», «лучший до 80»,
«что с Нурой», «сколько осталось»; в ответе `tools_used`; числа — через проверку чисел из `explainer.unknown_numbers`.

## Д-4. «Утвердить» и история — ✅ Claude

ГДЕ: `akim/approvals.py`, `tests/test_approvals.py`. Хранилище `var/approved.json` (в `.gitignore`).
ГОТОВО: `approve` недопустимого набора — ValueError с причиной; `approved()` возвращает утверждённые по порядку.

## Д-5. Запуск двумя способами — ✅ Claude (сборка Docker не проверена → Д-9)

ГДЕ: `Dockerfile`, `requirements.txt`, `.env.example`, README «Как запустить».
НЕЛЬЗЯ: настоящий `.env` в репозитории.
ГОТОВО: `docker build -t akim .` + `docker run -p 8501:8501 akim` и запуск без Docker открывают экран;
главный сценарий проходит без ключа.

## Д-6. Городские события и устойчивость — ✅ Claude

ГДЕ: `data/events.json`, `akim/events.py`, `tests/test_events.py`.
ГОТОВО: 3–4 события (зимний смог в Сарыарке, авария теплосети в Алматы, рост числа школьников в Есиле) как сдвиги
исходных показателей; `stress_test` — Score до и после события, новые критические и совет (лучшая замена одной меры
при событии); `sensitivity` — если вес направления выше на 20% (остальные пропорционально ниже): Score сценария и
лучший набор при таких весах. События — наши условные сценарии, в README раскрыть как придуманные командой.

## Д-7. Инструменты Аналитика и Стратега, паспорт, голос — ✅ Claude

ГДЕ: `akim/tools.py`, `akim/brief.py`, `akim/voice.py`, тесты.
ГОТОВО: `district_report`, `compare`, `what_if`, `find_best`, `frontier`, `brief`, `transcribe` по контракту;
`find_best(max_budget=80)` не возвращает наборов дороже 80; `find_best(exclude=["M3"])` — без ЛРТ.

## Д-8. Главный сценарий одной командой — ⬜ Дмитрий, до 14:40

ЦЕЛЬ: эксперт одной командой видит, что пять критериев ТЗ выполняются, — без ключей и без браузера.
ГДЕ: `scripts/check_scenario.py`, `tests/test_check_scenario.py`.
НЕЛЬЗЯ: `app.py`, README; числа, которых нет в эталоне ниже; писать в `var/`.
ГОТОВО: `python scripts/check_scenario.py` сам выключает модель (`AKIM_NO_LLM=1` до импорта `akim`), проходит шаги
и печатает по каждому «✓ шаг» или «✗ шаг: получили X, ждали Y»; код выхода 0, если всё сошлось, иначе 1:
1. `load_data()`: бюджет 100, 5 районов, 5 направлений — у всех одинаковые (критерий 1);
2. `baseline()`: 52.56, Нура 49.18, ниже 40 — два показателя (S1 и S2 в Нуре);
3. набор дороже 100 (из `tests/test_app.py`, 127) → `valid == False`, причина начинается с «Бюджет превышен» (критерий 2);
4. пример организаторов (M7 Нура, M8 Нура, M10 Нура, M12, M5 Сарыарка) → 56.54, бюджет 95, +3.98 (критерии 3 и 5);
5. `explain` → `mode == "template"`, сильные стороны, риски и последствия не пустые (критерий 4);
6. `improve` → замена M5 Сарыарка на M3 Нура, 57.21 (+0.67); `top(1)` → 57.24 из 694 395;
7. поручение «Улучши, но не ухудшай качество воздуха в Сарыарке» → `parse_request` → `run_mission`: статус ok,
   Проверяющий дважды, рекомендация 56.78, цена условий 0.46;
8. `approve` недопустимого набора → ValueError.
Тест запускает `main()` и ждёт 0. После — одна строка Claude: время прогона, чтобы вписать команду в README.

## Д-9. Чистый клон на ноутбуке Дмитрия — ⬜ Дмитрий, до 15:15

ЦЕЛЬ: проверить допуск (п. 5.4.16, 5.6.5) на чужой машине, как это сделает эксперт.
ГДЕ: пустая папка на ноутбуке Дмитрия, `git clone`, без `.env`; строго по README: «Быстрая проверка за 3 минуты»
и «Установка и запуск» — оба способа (обычный и Docker).
ГОТОВО: либо «прошло по README без единой правки» и время `docker build`, либо список «шаг → что получил → что
ожидал». Правки `Dockerfile` и `requirements.txt` — коммит Дмитрия; правки README — Claude.

## Д-10. Рейтинг команд — ⬜ Дмитрий, до 15:50

ЦЕЛЬ: опция ТЗ «сравнение результатов нескольких команд» — у всех одинаковые бюджет и данные (критерий 1), рейтинг
показывает, чей сценарий лучше и какое у него место среди всех 694 395 наборов.
ГДЕ: `akim/teams.py`, экспорт в `akim/__init__.py`, `tests/test_teams.py`. Хранилище `var/teams.json`
(`var/` уже в `.gitignore` и `.dockerignore`).
НЕЛЬЗЯ: `app.py`; в тестах писать в настоящий `var/` — подменять путь на временный.
ГОТОВО: `submit` и `leaderboard` ровно по контракту выше; место среди наборов — `akim.rank(plan)`, самый слабый
район — `min_district` из `evaluate`. Пример организаторов под командой «Terricon» → score 56.54, rank 566;
лучший набор под другой командой → первое место в рейтинге, rank 1; недопустимый набор и пустое имя — ValueError;
повторная отправка той же команды заменяет прежнюю.

---

## В-1. Сборка 5 решений — ✅ Codex, проверено Claude 14:00

ЦЕЛЬ: пользователь собирает 5 решений и видит бюджет и соблюдение правил.
ГДЕ: `app.py`, `tests/test_app.py`.
НЕЛЬЗЯ: считать бюджет или Score на экране; трогать `akim/`, `data/`, остальные тесты; коммитить.
ГОТОВО: 5 строк «мера + район»; поле района только у мер `scope == "district"`; подпись меры — id, название,
направление, стоимость, лаг, эффекты; полоса «потрачено N из 100» из `budget_used`; при `valid == False` — все
`errors[].message`; при `valid == True` — «Набор допустим». Тест (streamlit.testing.v1.AppTest): пример организаторов
→ «95 из 100» и «Набор допустим»; набор дороже 100 → причина «Бюджет превышен…».

## В-2. Экран результата — ✅ Codex, проверено Claude 14:00

ГДЕ: `app.py`, `tests/test_app.py`.
ГОТОВО: Score крупно и `delta` к 52.56; самый слабый район (`min_district`); число показателей ниже 40 и «было 2»;
таблица «район × показатель» до/после — ниже 40 красным, 40–45 жёлтым, изменившиеся выделены; D до → после;
вклад мер (`contributions`); синергии. Тест: пример → 56.54, +3.98, Нура 52.96.

## В-3. Разбор агента, поручение с журналом шагов, чат, голос — ✅ Codex, проверено Claude 14:16 (3 находки → в В-4)

ГДЕ: `app.py`, `tests/test_app.py`.
НЕЛЬЗЯ: менять набор без нажатия пользователя; считать что-то на экране.
ВАЖНО (проверка В-1/В-2, исправлено 14:16): выпадающие списки держат своё значение в `st.session_state["measure_i"]`
и `st.session_state["district_i"]`. Кнопки «Применить…» и «Взять» — через `on_click`: в обработчике обновить и `plan`,
и эти ключи, **без `st.rerun()`** (страница перезапустится сама; `st.rerun()` в обработчике не работает и выводит на
страницу жёлтое «Calling st.rerun() within a callback is a no-op.»). Старые предложения («improvement»,
«mission_result») при этом убрать. Вне обработчика ключи выпадающих списков менять нельзя.
ГОТОВО:
- блоки «сильные стороны / риски / последствия» из `akim.explain`, пометка «модель» или «шаблон (без ключа)»;
  «Улучшить сценарий» — замена и прирост из `akim.improve`, набор меняется только кнопкой «Применить»;
- **«Поручение агенту»** — поле текста («Улучши, но не ухудшай воздух в Сарыарке»; «Школу в Нуре сохрани, ЛРТ исключи,
  потрать не больше 95») → `akim.parse_request` → показать понятые условия → `akim.run_mission(plan, request)` →
  **журнал шагов** (`steps`: роль, действие, результат — по порядку, как лента статусов `st.status`), рекомендация и
  альтернатива, «цена ваших условий» (`price`), «что ухудшится» (`warnings`); при `status == "infeasible"` — честное
  «условия невыполнимы» без рекомендации; кнопка «Применить рекомендацию» ставит `suggestion` в набор;
- чат `st.chat_input` + `st.chat_message` через `akim.chat`, под ответом — `tools_used`, при `mission` — тот же журнал
  шагов, при `suggestion` — кнопка «Применить предложение», при `note` — серая подпись;
- голос `st.audio_input` → `akim.transcribe` → текст в чат; без ключа — подпись «голос работает с ключом OpenAI».
Тест без ключа: пометка «шаблон»; поручение «не ухудшай качество воздуха в Сарыарке» на примере даёт журнал, где
Проверяющий дважды, и рекомендацию 56.78 с ценой условий 0.46.

## В-4. Сравнение, топ-5, «Утвердить» — 🔨 Codex

ГДЕ: `app.py`, `tests/test_app.py`.
ГОТОВО: «Запомнить как A» и сравнение через `akim.compare`; топ-5 из `akim.top(5)` с кнопкой «Взять этот набор»;
«Утвердить сценарий» активна только при `valid == True`, вызывает `akim.approve`, показывает время и Score; ниже —
`akim.approved()`. Тест: топ-1 = 57.24; недопустимый набор утвердить нельзя.

## В-5. Подбор под цель, карта, паспорта, события — ⬜

ГДЕ: `app.py`, `tests/test_app.py`.
ГОТОВО: вкладка «Подбор под цель» (бюджет не больше, обязательно, исключить, ни один район не ниже) →
`akim.find_best` → 5 наборов с кнопкой «Взять»; график «бюджет → лучший Score» из `akim.frontier()`; схема 5 районов
(не настоящая карта), цвет по D до/после; выбор района → `akim.district_report`; городские события из
`akim.events()` → `akim.stress_test`; «Скачать паспорт» — `st.download_button` с `akim.brief(plan)`.
Тест: подбор с бюджетом 80 не даёт наборов дороже 80; паспорт скачивается.

## В-6. Рейтинг команд — ⬜ (после Д-10)

ГДЕ: `app.py`, `tests/test_app.py`.
ГОТОВО: поле «Название команды» и кнопка «Отправить в рейтинг» (активна только при `valid == True`) →
`akim.submit(team, plan)`; ниже таблица `akim.leaderboard()`: место, команда, Score, прирост, место среди 694 395,
бюджет, самый слабый район. Ошибка `submit` — текст причины на экране. Тест: пример под «Terricon» → в таблице 56.54
и 566; хранилище в тесте — временный файл.
