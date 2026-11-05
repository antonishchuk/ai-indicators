# AI Leading Indicators — план проекта

Дата: 2026-11-05. Источники ниже проверены живыми запросами в этот день.

## 1. Идея

Один экран с опережающими индикаторами AI-цикла. Две главные оси:

- **Compute (предложение)** — цена аренды GPU, спред spot/list, доступность, вторичка.
- **Tokens (спрос / коммодитизация)** — цены токенов, cost-per-intelligence, темп релизов.

Плюс вспомогательные панели: цепочка поставок (TSMC/HBM), capex и финансирование, энергия, adoption.

Для каждого ряда храним историю, считаем изменение за 7/30/90 дней и z-score, подсвечиваем аномалии и шлём алерт в Telegram при смене цены.

## 2. Индикаторы

### 2.1 Compute: аренда GPU ($/GPU-час)

| Индикатор | Источник | Эндпоинт | Ключ | Частота |
|---|---|---|---|---|
| Индекс H100 SXM / H200 / B200 (транзакционный, Bloomberg-listed) | Ornn OCPI | `GET https://api.ornnai.com/api/gpu/H100%20SXM` (и `H200`, `B200`) | нет | ежечасно, храним daily close |
| min/p25/median/p75/max по 31 провайдеру, H100/H200/B200 | gpuperhour.com | `https://api.gpuperhour.com/api/price-index/export.csv?days=365` | нет | daily, бэкфилл 365 дней |
| List-цены neocloud: H100/H200/B200/B300 secure + community | RunPod GraphQL | `POST https://api.runpod.io/graphql` query `{ gpuTypes { id displayName securePrice communityPrice secureSpotPrice communitySpotPrice } }` | нет | live |
| Hyperscaler on-demand + spot: H100, H200, GB200 | Azure Retail Prices | `https://prices.azure.com/api/retail/prices` с `$filter=armRegionName eq 'eastus' and contains(armSkuName,'H100')` (и H200, GB200) | нет | live |
| AWS spot p5 (H100), p5en (H200), p6-b200 | AWS spot.json | `https://website.spot.ec2.aws.a2z.com/spot.json` | нет | несколько раз в день |
| Второй независимый индекс H100/H200/B200 | Silicon Data | HTML `https://www.silicondata.com/products/silicon-index/h100` (значение в server-rendered HTML) | нет | business-daily |
| Blackwell Ultra list: B300, GB200, GB300 по провайдерам | amcompute.com | `https://www.amcompute.com/gpu-cloud-prices/data.csv` | нет (attribution) | ~monthly |
| Доступность (есть ли сток по регионам) | Lambda `instance-types`, Shadeform `/v1/instances/types` | бесплатный ключ | live |

**Производные ряды (считаем сами):**

- `spot/list spread` H100 = Ornn index / RunPod securePrice. Падает — переизбыток мощностей.
- `gen ratio` B200/H100, H200/H100 — кривая устаревания. Сужается — старое поколение не нужно.
- `hyperscaler premium` = Azure on-demand per GPU / Ornn index — насколько neocloud дешевле.
- `spot discount` = AWS spot / on-demand для p5.
- `availability %` — доля регионов Lambda с capacity.

**Вторичка (v2, сложно):** amcompute appraisal H100 (~$14k used, HTML), eBay Browse API (только активные листинги, asking), SMM China headlines (H200 PCIe ¥385k/карта). Реальных sold-данных бесплатно нет.

**Недоступно бесплатно:** закупочные цены B200/B300/GB200 (только оценки аналитиков), аренда Rubin/VR200 (никто не публикует), lead times.

### 2.2 Tokens: цены $/1M

| Индикатор | Источник | Эндпоинт | Ключ | Частота |
|---|---|---|---|---|
| Все модели (455), cheapest-routed цена + `created` | OpenRouter | `GET https://openrouter.ai/api/v1/models` (цены в $/токен, ×1e6) | нет | daily |
| First-party list price для open-weight (DeepSeek, Kimi, Qwen, GLM, MiniMax) | OpenRouter endpoints | `GET /api/v1/models/{author}/{slug}/endpoints`, фильтр `provider_name` == вендор | нет | daily, ~40 вызовов |
| Второй источник + бэкфилл с 2024-01 | LiteLLM | `raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json`; история через `api.github.com/repos/BerriAI/litellm/commits?path=...` | нет | daily |
| Кураторский лог датированных изменений | llm-prices.com | `https://www.llm-prices.com/current-v1.json`, `historical-v1.json` | нет | weekly |
| Off-peak / tiers / batch нюансы | pydantic genai-prices | `raw.githubusercontent.com/pydantic/genai-prices/main/prices/new_data/v2/data.json` | нет | weekly |
| Intelligence index + tok/s + цена в одной строке | Artificial Analysis | `GET https://artificialanalysis.ai/api/v2/language/models/free` | бесплатный ключ, 100 req/день, attribution | daily |
| Официальные страницы как ground truth | OpenAI `developers.openai.com/api/docs/pricing`, Anthropic `platform.claude.com/docs/en/about-claude/pricing`, DeepSeek `api-docs.deepseek.com/quick_start/pricing` | статичный HTML | нет | daily, только детект изменений |

Официальная страница Kimi JS-rendered — берём через OpenRouter endpoint `Moonshot AI` и genai-prices.

**Корзина (~40 моделей):** флагман + mid + small у OpenAI, Anthropic, Google, xAI, Mistral; все актуальные DeepSeek, Kimi, Qwen, GLM, MiniMax, Llama.

**Производные ряды:**

- `frontier price` — средняя output-цена топ-3 по AA intelligence index. Главный ряд.
- `cost per intelligence point` — price / AA index, по вендорам. «Кривая дефляции интеллекта».
- `open vs closed gap` — медиана output-цены open-weight / closed при сопоставимом index.
- `OR routed vs list` — cheapest-routed / first-party. Сжатие = маржа инференса давится.
- `output/input ratio` — тренд ценообразования.
- `release cadence` — новых моделей в месяц по `created` в OpenRouter.
- `price-cut events` — лента: модель, дата, старое → новое. Алерт в Telegram.

Детектор изменений: пишем (source, model_id, date, in, out, cache_read, cache_write); событие только если ≥2 источника согласны или источник first-party. Иначе ложные срабатывания от churn ключей LiteLLM и смены хоста в OpenRouter.

### 2.3 Дополнительные индикаторы (предложение)

**Цепочка поставок**

| Индикатор | Зачем | Источник |
|---|---|---|
| TSMC monthly revenue, YoY | опережает квартальные отчёты NVDA | `investor.tsmc.com/english/monthly-revenue` HTML/XLSX, ~10 числа |
| HBM $/GB (HBM3E, HBM4) | узкое место Blackwell/Rubin | Silicon Analysts `siliconanalysts.com/market-data/hbm-pricing` (последние точки бесплатно) |
| Korea semiconductor exports (first 20 days) | самый ранний месячный сигнал по памяти | Korea Customs Service, пресс-релиз 21 числа; парсить |
| TrendForce headlines (DRAM/HBM contract) | текстовые алерты | RSS `trendforce.com/feed/Semiconductors.html` |
| Micron / SK hynix revenue, guidance | HBM-капасити | EDGAR XBRL (Micron CIK 723125), DART API для SK hynix |

**Capex и финансирование**

| Индикатор | Зачем | Источник |
|---|---|---|
| Capex MSFT/GOOGL/META/AMZN/ORCL, сумма и YoY | главный спрос на GPU | `data.sec.gov/api/xbrl/companyconcept/CIK.../us-gaap/PaymentsToAcquirePropertyPlantAndEquipment.json` (Amazon: `PaymentsToAcquireProductiveAssets`) |
| Neocloud кредитный стресс: CRWV, ORCL, NBIS vs HY-спред | долг neocloud ломается первым | Yahoo chart API + FRED `BAMLH0A0HYM2` (бесплатный ключ) |
| AI-корзина vs SPX: NVDA, AMD, AVGO, TSM, MU, SMCI, VRT, CRWV; SMH/SPY | относительная сила | `query1.finance.yahoo.com/v8/finance/chart/{t}` |
| NVDA implied vol, forward P/E | sentiment | `yfinance` (options требуют crumb) |

**Энергия (v2)**

| Индикатор | Источник |
|---|---|
| PJM capacity auction price, цена электроэнергии PJM/ERCOT | EIA API (бесплатный ключ), отчёты PJM |
| Henry Hub | FRED `DHHNGSP` |

**Adoption / объём спроса на токены**

| Индикатор | Зачем | Источник |
|---|---|---|
| OpenRouter rankings: токены/неделю по модели и вендору | прямой объём спроса | `openrouter.ai/rankings` — проверить, есть ли JSON; иначе scrape |
| PyPI downloads `openai`, `anthropic`, `litellm`, `langchain` | developer adoption | `pypistats.org/api/packages/{pkg}/recent`, без ключа |
| npm downloads `openai`, `@anthropic-ai/sdk`, `ai` | то же для JS | `api.npmjs.org/downloads/point/last-week/{pkg}` |
| Hugging Face downloads топ open-weight моделей | спрос на open-weight | `huggingface.co/api/models?sort=downloads&limit=50` |
| GitHub stars velocity ключевых репо | hype-прокси | GitHub API |
| Polymarket: «лучшая модель на конец года», «OpenAI IPO», «NVDA market cap» | рыночные ожидания | Gamma API `gamma-api.polymarket.com/markets` (есть репо Polymarket) |
| AI job postings share | спрос на труд | Indeed Hiring Lab GitHub CSV |

**Композит:** для каждого ряда z-score к 1-летнему окну, затем взвешенный «AI cycle heat» по группам: Compute tightness, Token deflation, Supply chain, Capex, Adoption. Показываем как 5 стрелок + общий гейдж. Веса ручные, без ML.

## 3. Архитектура

Рекомендация: **git-as-database + GitHub Actions + GitHub Pages**. Ноль серверов, ноль денег, не трогаем торговый VDS.

```
ai-indicators/
  collectors/        # один модуль на источник, возвращает list[Row]
    base.py          # Row(ts, source, series_id, value, unit, meta)
    openrouter.py, litellm.py, llm_prices.py, genai_prices.py, aa.py
    ornn.py, gpuperhour.py, runpod.py, azure.py, aws_spot.py, silicondata.py, amcompute.py
    edgar.py, tsmc.py, yahoo.py, fred.py, pypistats.py, npm.py, hf.py, polymarket.py
  derive/            # производные ряды, z-scores, детектор событий, композит
  data/
    raw/YYYY-MM-DD/<source>.json    # сырые снапшоты (для переразбора)
    series.parquet                  # нормализованные ряды
    events.jsonl                    # price-cut events
  site/              # статический дашборд, читает data/*.json
  scripts/           # backfill_litellm.py, backfill_gpuperhour.py, backfill_wayback_openrouter.py
  .github/workflows/collect.yml     # cron 06:00 UTC daily → collect → derive → commit → deploy Pages
```

- Python 3.12, `httpx`, `polars`, `pydantic`. Без БД — parquet в репо.
- Дашборд: статичный HTML + Plotly.js или uPlot. Вкладки: Overview / Compute / Tokens / Supply chain / Capex / Adoption. Overview — плитки с 30d/90d изменением и спарклайном.
- Алерты: Telegram bot (код из Execution_TCS переиспользуем).
- Секреты в GitHub Secrets: AA key, FRED key, Telegram token. Остальное без ключей.
- Правило: сырые ответы всегда сохраняем, нормализация переделывается из raw.

Альтернатива — FastAPI на VDS в docker, как Execution_TCS. Нужна, только если захочется интрадей-поллинг или серверный интерактив. Для daily не нужна.

## 4. Фазы

**Фаза 0 — каркас (1 вечер).** Репо, `Row`, раннер коллекторов, parquet, workflow с cron и commit-back. Один коллектор (OpenRouter) end-to-end.

**Фаза 1 — Tokens (неделя).** OpenRouter + endpoints first-party, LiteLLM, llm-prices, genai-prices, AA (зарегистрировать ключ). Бэкфилл: LiteLLM git history по ~40 ключам + llm-prices historical + Wayback OpenRouter (33 месячных снапшота с 2023-07). Детектор событий, Telegram.

**Фаза 2 — Compute (неделя).** Ornn, gpuperhour (бэкфилл 365 дней), RunPod, Azure, AWS spot, Silicon Data scrape, amcompute CSV. Производные: spread, gen ratio, hyperscaler premium.

**Фаза 3 — Macro (неделя).** EDGAR capex 5 компаний, TSMC revenue, Yahoo корзина, FRED HY. Опционально HBM, Korea exports, TrendForce RSS.

**Фаза 4 — Дашборд + композит.** Static site, плитки, z-scores, «AI cycle heat». GitHub Pages.

**Фаза 5 — Adoption.** PyPI/npm/HF, OpenRouter rankings, Polymarket, Indeed.

## 5. Ограничения и ToS

- Vast.ai ToS прямо запрещает scraping и построение индексов. Не использовать в публичной версии.
- Artificial Analysis и amcompute требуют attribution в футере.
- EDGAR требует описательный User-Agent с email.
- Silicon Data: проверить ToS перед scrape; значения есть в HTML без JS.
- Платное, не берём: Ornn Premium ($500/мес), computeprices ($79), getdeploying ($499), SemiAnalysis, TrendForce, DRAMeXchange.

## 6. Сырые снапшоты от 2026-11-05 (день 0)

Лежат в scratchpad сессии, скопировать в `data/raw/2026-11-05/`:
`C:\Users\aonis\AppData\Local\Temp\claude\d--Github-Execution-TCS\e3dd42c7-06f1-4e6d-b991-b0254a857ede\scratchpad\` — or_models.json, litellm.json, current-v1.json, historical-v1.json, aa_openapi.json, pk.json, плюс ответы Vast / AWS spot / Silicon Data.

## 7. Контрольные значения на 2026-11-05

- GPU $/час: Ornn H100 SXM 2.64, H200 6.36, B200 9.48; RunPod secure H100 SXM 3.99, H200 5.29, B200 7.99, B300 8.99; Silicon Data H100 2.96; Nebius B300 9.50; CoreWeave GB200 10.50.
- Tokens $/1M in/out: GPT-6-astra 10/50, GPT-6.1-sol 2/10; Claude Fable 5.1 10/50, Opus 5.5 4/20, Sonnet 5.5 2/10, Haiku 5.5 0.10/0.50; DeepSeek V4-Pro 1.32/3.96 (off-peak 50%), deepseek-flash 0.30/1.20; Kimi k3.1-pro 2/10, k3 3/15.
- Macro: NVDA 200.13; TSMC Sep revenue NT$511.9B (+54.6% YoY); MSFT capex Q1 FY27 $39.4B.
