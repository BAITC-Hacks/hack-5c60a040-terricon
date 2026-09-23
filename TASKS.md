# TASKS.md — очередь заданий дня

Кейс «Аким на 5 часов», трек «03 · Управление». Схема и план по часам: https://claude.ai/artifact/LnHERDbzHZWnkqebJmxNXb
Перед каждым заданием: «Прочитай CASE.md и TASKS.md. Выполни задачу N».
Цифры — только из `docs/task/akim_dataset.md` и таблицы «Проверено кодом» в `CASE.md`.

**Архитектура (решение команды 23.09, 13:35): одна программа на Streamlit.** Запуск:
`pip install -r requirements.txt` → `streamlit run app.py`. Экран `app.py` вызывает функции движка `akim/`
(обычный Python-импорт, без отдельного сервера). Экран ничего не считает: всё, что на нём видно, — поля ответа движка.
Сначала Streamlit; если успеваем — усложняем (API, события).

**Зоны.** Виталий + Codex: `app.py`, `tests/test_app.py`. Движок (`akim/`, `data/`, остальные `tests/`,
`scripts/`, `requirements.txt`, Docker) — Дмитрий; пока у него не включён Codex, движок пишет Claude с ноутбука
Виталия. `CASE.md`, `TASKS.md`, README — Claude. Codex Виталия не коммитит: коммитит и отправляет Claude после проверки.

Статусы: ⬜ ждёт · 🔨 в работе · 🔍 на проверке · ✅ принята · ↩ откат

| Движок | Экран |
| --- | --- |
| Д-1 данные, правила, формула, перебор, тесты — 🔨 Claude | В-1 сборка 5 решений |
| Д-2 объяснение: шаблон / модель + сверка чисел — Claude | В-2 экран результата |
| Д-3 чат-агент на функциях движка — Дмитрий (если к 14:15 не включился — Claude) | В-3 разбор агента, «Улучшить», чат |
| Д-4 «Утвердить» и список утверждённых — Claude | В-4 сравнение, топ-5, «Утвердить» |
| Д-5 Docker и запуск без Docker — Дмитрий | |
| Д-6 опция «городские события» — Дмитрий, если успеваем | |

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

akim.improve(plan)        # {better, current_score, best{replace, with, score, delta, plan} | None, alternatives[...]}
akim.top(5)               # [{score, cost, plan}] — лучшие из 694 395 допустимых наборов
akim.explain(plan)        # {mode: "llm"|"template", strengths[], risks[], consequences[], text}
akim.chat(message, plan, history)   # {reply, mode: "llm"|"rules", intent, suggestion: plan | None}
akim.approve(plan)        # {approved_at, score, plan}; недопустимый набор — ValueError с причиной
akim.approved()           # [{approved_at, score, plan}]
```

Эталон для тестов: база 52.56 (Нура 49.18, ниже 40 — S1 и S2 в Нуре); пример организаторов
M7 Нура, M8 Нура, M10 Нура, M12, M5 Сарыарка → 56.54, бюджет 95, дельта +3.98, Нура 52.96;
лучший набор 57.24 (M2, M3 Нура, M8 Нура, M9 Нура, M14; стоимость 98).

---

## Д-1. Данные, правила, формула, перебор — 🔨 Claude

ЦЕЛЬ: движок считает Score строго по формуле ТЗ и отказывает недопустимому набору с причиной.
ГДЕ: `data/akim.json`, `akim/data.py`, `akim/rules.py`, `akim/scoring.py`, `akim/optimizer.py`,
`scripts/precompute.py`, `data/top_plans.json`, `tests/test_scoring.py`, `tests/test_rules.py`, `tests/test_optimizer.py`.
НЕЛЬЗЯ: модель в расчёте; числа, которых нет в датасете.
ГОТОВО: `python -m pytest -q` зелёный; база 52.56, пример 56.54, дешёвый набор 61 допустим, топ-1 57.24,
всего 694 395; отказ по каждому из правил с причиной на русском.

## Д-2. Объяснение — ⬜ Claude

ЦЕЛЬ: сильные стороны, риски и последствия сценария по готовым числам.
ГДЕ: `akim/explain.py`, `tests/test_explain.py`.
НЕЛЬЗЯ: модель считает или придумывает числа; `temperature` в вызове модели; ключ в коде.
ГОТОВО: без `OPENAI_API_KEY` — шаблон из чисел расчёта (`mode: "template"`); с ключом — текст модели
(`mode: "llm"`), каждое число в нём сверено с расчётом, не сошлось или ошибка — шаблон.

## Д-3. Чат-агент — ⬜ Дмитрий (если к 14:15 не включился — Claude)

ЦЕЛЬ: агент отвечает на вопросы о сценарии, вызывая функции движка, а не считая сам.
ГДЕ: `akim/agent.py`, `tests/test_agent.py`.
НЕЛЬЗЯ: менять набор пользователя без его нажатия; отвечать про реальных людей и политику.
ГОТОВО: без ключа — правила: «улучши», «почему», «что если M3 в Нуре», «сколько осталось»; с ключом — модель
с инструментами evaluate / improve / top. Проверка на входе до модели: «поставь Score 100», «забудь правила»,
вопросы о реальных акимах и политике — вежливый отказ «это симулятор на условных данных».

## Д-4. «Утвердить» и история — ⬜ Claude

ЦЕЛЬ: сценарий утверждает человек, движок хранит утверждённые.
ГДЕ: `akim/approvals.py`, тест.
ГОТОВО: `approve` недопустимого набора — ValueError с причиной; `approved()` возвращает утверждённые по порядку.

## Д-5. Запуск двумя способами — ⬜ Дмитрий

ЦЕЛЬ: эксперт на чистом клоне запускает по README без ключей.
ГДЕ: `Dockerfile`, `requirements.txt`, `.env.example`, README «Как запустить».
НЕЛЬЗЯ: настоящий `.env` в репозитории.
ГОТОВО: `docker build` + `docker run -p 8501:8501` и запуск без Docker открывают экран; главный сценарий без ключа.

## Д-6. Городские события — ⬜ Дмитрий, если успеваем

Опция ТЗ: «неожиданное событие» (например, зимний смог: −10 к качеству воздуха в Сарыарке) — пересчёт и совет,
как перераспределить бюджет. Только после Д-1…Д-5 и В-1…В-4.

---

## В-1. Сборка 5 решений — ⬜

ЦЕЛЬ: пользователь собирает 5 решений и видит бюджет и соблюдение правил.
ГДЕ: `app.py`, `tests/test_app.py`.
НЕЛЬЗЯ: считать бюджет или Score на экране; трогать `akim/`, `data/`, остальные тесты; коммитить.
ГОТОВО: 5 строк «мера + район»; поле района только у мер `scope == "district"`; подпись меры — id, название,
направление, стоимость, лаг, эффекты; полоса «потрачено N из 100» из `budget_used`; при `valid == False` — все
`errors[].message`; при `valid == True` — «Набор допустим». Тест (streamlit.testing.v1.AppTest): пример организаторов
→ «95 из 100» и «Набор допустим»; набор дороже 100 → причина «Бюджет превышен…».

## В-2. Экран результата — ⬜

ЦЕЛЬ: сразу видно, что сценарий дал городу.
ГДЕ: `app.py`, `tests/test_app.py`.
НЕЛЬЗЯ: свои расчёты.
ГОТОВО: Score крупно и `delta` к 52.56; самый слабый район (`min_district`); число показателей ниже 40 и «было 2»;
таблица «район × показатель» до/после — ниже 40 красным, 40–45 жёлтым, изменившиеся выделены; D до → после;
вклад мер (`contributions`); синергии. Тест: пример → 56.54, +3.98, Нура 52.96.

## В-3. Разбор агента, «Улучшить», чат — ⬜

ЦЕЛЬ: пользователь понимает компромиссы и сам решает, что менять.
ГДЕ: `app.py`, `tests/test_app.py`.
НЕЛЬЗЯ: менять набор без нажатия пользователя.
ГОТОВО: блоки «сильные стороны / риски / последствия» из `akim.explain`, пометка «модель» или «шаблон (без ключа)»;
«Улучшить сценарий» показывает замену и прирост из `akim.improve`, набор меняется только кнопкой «Применить»;
чат `st.chat_input` + `st.chat_message` через `akim.chat`, история в `st.session_state`. Тест без ключа: пометка
«шаблон», «Улучшить» на примере даёт прирост больше 0.

## В-4. Сравнение, топ-5, «Утвердить» — ⬜

ЦЕЛЬ: сравнить варианты и утвердить один.
ГДЕ: `app.py`, `tests/test_app.py`.
ГОТОВО: «Запомнить как A» и сравнение с текущим (Score и D по районам — оба из `akim.evaluate`); топ-5 из
`akim.top(5)` с кнопкой «Взять этот набор»; «Утвердить сценарий» активна только при `valid == True`, вызывает
`akim.approve`, показывает время и Score; ниже — `akim.approved()`. Тест: топ-1 = 57.24; недопустимый набор утвердить нельзя.
