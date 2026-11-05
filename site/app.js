/* AI Leading Indicators dashboard. Data: data/dashboard.json built by aiind/build_site.py */
(function () {
  "use strict";

  // ------------------------------------------------------------ card config
  // kind: lines | bars | grouped | stacked | table | events
  const CARDS = [
    // ---- Compute
    {
      id: "gpu_h100", section: "compute", kind: "lines", title: "Аренда H100 SXM", unit: "$/GPU-час",
      what: "Цена часа аренды одного H100 SXM. Медиана и минимум предложений примерно 30 облаков (gpuperhour), транзакционный индекс Ornn (реальные сделки) и list-цена RunPod.",
      read: "Это спотовый рынок вычислений. Падение цены при растущем числе продавцов означает переизбыток мощностей: спрос на обучение и инференс не успевает за поставками, маржа neocloud (CoreWeave, Lambda, Nebius) сжимается, а за ней заказы на новые GPU. Рост цены означает дефицит. Смотрите тренд за 30 и более дней, а не дневной шум.",
      caveat: "Цены предложения, а не сделки, кроме индекса Ornn. Индекс Ornn обновляется ежечасно и за день может сдвинуться на 10 и более процентов.",
      src: "gpuperhour.com, api.ornnai.com, RunPod GraphQL",
    },
    {
      id: "gpu_ladder", section: "compute", kind: "grouped", title: "Лестница поколений", unit: "$/GPU-час, последнее значение",
      what: "Текущая цена часа для H100 PCIe, H100 SXM, H200, B200 и B300 из трёх источников.",
      read: "Показывает, какую премию рынок платит за новое поколение. Если B200 стоит лишь немного дороже H100, спрос на Blackwell слаб или предложение выросло быстрее спроса. Большой разрыв означает, что новые чипы в дефиците и парк H100 быстро обесценивается.",
      caveat: "Индекс Ornn покрывает только H100 SXM, H200 и B200. Для B300 данных мало, медиана может строиться по 2 или 3 предложениям.",
      src: "gpuperhour.com, RunPod, Ornn",
    },
    {
      id: "gpu_gen_ratio", section: "compute", kind: "lines", title: "Премия Blackwell", unit: "отношение медианных цен",
      what: "Во сколько раз час B200, B300 и H200 дороже часа H100 SXM по медианам gpuperhour.",
      read: "Сжатие отношения означает, что новое поколение дешевеет быстрее старого или старое держит цену: спрос на новейшие чипы слабеет. Расширение означает обратное. Отношение также показывает скорость устаревания парка H100, который служит залогом по кредитам neocloud: чем ниже H100 относительно B200, тем хуже их балансы.",
      caveat: "История начинается с сентября 2026, когда gpuperhour ввёл текущую корзину.",
      src: "gpuperhour.com",
    },
    {
      id: "gpu_depth", section: "compute", kind: "lines", title: "Число провайдеров с GPU в продаже", unit: "провайдеров",
      what: "Сколько облаков из покрытия gpuperhour предлагают H100 SXM, H200 и B200 на данный день.",
      read: "Рост числа продавцов означает расширение предложения, обычно за ним следует снижение цен. Резкое падение числа предложений при росте цены означает дефицит: мощности раскуплены. Полезно читать вместе с графиком цены H100.",
      caveat: "Охват около 30 провайдеров, hyperscalers не входят.",
      src: "gpuperhour.com",
    },

    // ---- Tokens
    {
      id: "tok_frontier", section: "tokens", kind: "lines", log: true, wide: true, title: "Frontier-модели: цена output-токенов", unit: "$/1M токенов, лог-шкала",
      what: "Для каждого вендора линия показывает цену самой сильной модели на каждый момент времени: например GPT-4, затем GPT-4 Turbo, GPT-4o, GPT-5, GPT-5.5, GPT-6 Astra. Наведите курсор, чтобы увидеть модель.",
      read: "Цена frontier не падает монотонно, она колеблется: лаборатории берут премию за лучшую модель. Рост премии (как с GPT-6 Astra и Claude Fable по 50 долларов) означает ценовую власть и спрос на топовые модели, это поддерживает тезис о capex. Устойчивое падение означает коммодитизацию верхнего сегмента. Расхождение между западными и китайскими линиями показывает конкурентное давление.",
      caveat: "Источник LiteLLM, снимки раз в неделю, поэтому даты точны до недели. Уровень модели задан вручную, см. раздел Метод.",
      src: "LiteLLM model_prices (git history)",
    },
    {
      id: "tok_mid", section: "tokens", kind: "lines", log: true, title: "Workhorse-модели: output", unit: "$/1M токенов, лог-шкала",
      what: "Основная рабочая модель вендора: GPT-4o, затем GPT-5 и GPT-6 Sol у OpenAI, линейка Sonnet у Anthropic, Gemini Flash у Google, Mistral Medium.",
      read: "Это цена интеллекта для массового применения. Устойчивое снижение означает дефляцию стоимости инференса: чтобы выручка лабораторий росла, объём токенов должен расти быстрее, чем падает цена. Паузы и повышения означают, что мощностей не хватает или конкуренция ослабла.",
      caveat: "Сравнение между вендорами условно, потому что модели одного уровня различаются по качеству.",
      src: "LiteLLM (git history)",
    },
    {
      id: "tok_small", section: "tokens", kind: "lines", log: true, title: "Дешёвые модели: output", unit: "$/1M токенов, лог-шкала",
      what: "Самая дешёвая актуальная модель вендора: GPT-4o mini, затем nano и Luna у OpenAI, Haiku, Gemini Flash-Lite, DeepSeek Flash, Qwen Flash, Mistral Small.",
      read: "Нижняя граница рынка. Здесь видна гонка к нулю: насколько дёшево можно купить базовый интеллект. Сближение нижней границы с workhorse-уровнем означает, что дешёвые модели догнали по качеству и давят на цены середины.",
      caveat: "У некоторых вендоров ряд короткий, потому что дешёвая линейка появилась недавно.",
      src: "LiteLLM (git history)",
    },
    {
      id: "tok_frontier_input", section: "tokens", kind: "lines", log: true, title: "Frontier-модели: цена input-токенов", unit: "$/1M токенов, лог-шкала",
      what: "То же, что frontier output, но для входных токенов.",
      read: "Агентные нагрузки читают во много раз больше, чем пишут, поэтому для них важнее цена input. Input дешевеет быстрее output благодаря кэшированию и батчингу. Разрыв между input и output растёт, когда лаборатории зарабатывают на длинных рассуждениях модели.",
      caveat: "Без учёта кэша: с кэшированием эффективная цена input в 4-10 раз ниже.",
      src: "LiteLLM (git history)",
    },
    {
      id: "tok_open_discount", section: "tokens", kind: "lines", log: true, title: "Open-weight против закрытых", unit: "отношение цен output",
      what: "Цена output frontier-модели DeepSeek, Kimi, Qwen и MiniMax, делённая на среднюю цену workhorse-моделей OpenAI, Anthropic и Google.",
      read: "Меньше 1 означает, что китайская open-weight модель дешевле западного рабочего уровня. Падение отношения означает усиление ценового давления на закрытые лаборатории. Рост, как после выхода DeepSeek V4 Pro, означает, что open-weight лаборатории тоже начали брать премию, и ценовая война ослабла. Это один из самых прямых индикаторов конкуренции в отрасли.",
      caveat: "Сравниваются разные уровни намеренно: frontier open-weight обычно конкурирует с mid закрытых по качеству.",
      src: "LiteLLM (git history)",
    },
    {
      id: "tok_or_market", section: "tokens", kind: "table", title: "Рынок инференса open-weight моделей", unit: "OpenRouter, сегодня",
      what: "Для каждой открытой модели: сколько провайдеров её хостят на OpenRouter, минимальная и медианная цена output у них, и цена самого вендора, если он тоже хостит.",
      read: "Число провайдеров показывает конкуренцию в инференсе. Разрыв между минимумом и ценой вендора показывает маржу хостинга. Рост числа провайдеров при падении медианы означает коммодитизацию инференса: хорошо для объёмов GPU, плохо для цен. Если минимум сильно ниже медианы, дешёвые хосты часто используют квантованные версии модели.",
      caveat: "Снимок на день, история накапливается с запуска дашборда.",
      src: "openrouter.ai/api/v1/models/{id}/endpoints",
    },
    {
      id: "tok_events", section: "tokens", kind: "events", title: "Лента изменений цен", unit: "последние 60 событий по отслеживаемым моделям",
      what: "Моменты, когда цена уже существующей модели изменилась. Дата это неделя снимка, в которую изменение впервые видно.",
      read: "Снижение цены действующей модели это прямой сигнал конкуренции или падения себестоимости инференса. Повышения редки и означают дефицит мощностей или уверенность в спросе. Серия снижений у одного вендора обычно предшествует запуску нового поколения.",
      caveat: "Часть событий это исправления ошибок в самом LiteLLM, а не реальные изменения. Сверяйте с официальными страницами.",
      src: "LiteLLM (git history)",
    },
    {
      id: "tok_releases", section: "tokens", kind: "bars_lines", title: "Темп релизов", unit: "новых моделей в месяц на OpenRouter",
      what: "Сколько новых моделей появилось на OpenRouter в месяц: все авторы и отдельно крупные лаборатории (OpenAI, Anthropic, Google, xAI, DeepSeek, Moonshot, Qwen, Z.ai, MiniMax, Meta, Mistral).",
      read: "Прокси интенсивности гонки. Ускорение релизов крупных лабораторий означает, что циклы обучения укорачиваются и конкуренция растёт. Замедление означает консолидацию или переход к более длинным и дорогим циклам обучения, что поддерживает спрос на вычисления.",
      caveat: "Последний месяц неполный. Варианты моделей (free, batch) не считаются.",
      src: "openrouter.ai/api/v1/models, поле created",
    },

    // ---- Supply chain, capex, financing
    {
      id: "tsmc_rev", section: "supply", kind: "bars", title: "TSMC: месячная выручка", unit: "NT$ млрд, в подсказке YoY",
      what: "Консолидированная месячная выручка TSMC, публикуется около 10 числа следующего месяца.",
      read: "TSMC производит все чипы NVIDIA, AMD, Broadcom и Google TPU, поэтому его выручка это самый ранний твёрдый сигнал по физическому объёму AI-железа, на 1-2 месяца раньше квартальных отчётов. Замедление роста YoY при по-прежнему высоком capex означает, что пик цикла близко. Ускорение подтверждает, что заказы превращаются в поставки.",
      caveat: "Выручка в тайваньских долларах, есть сезонность (февраль, конец кварталов) и эффект цен на передовые техпроцессы.",
      src: "investor.tsmc.com/english/monthly-revenue",
    },
    {
      id: "capex", section: "supply", kind: "stacked", wide: true, title: "Capex hyperscalers", unit: "$ млрд за квартал, Microsoft, Alphabet, Meta, Amazon, Oracle",
      what: "Квартальные капитальные затраты пяти крупнейших покупателей GPU из отчётов SEC. Сумма и её изменение к тому же кварталу год назад показаны в подсказке.",
      read: "Это главный источник спроса на GPU и дата-центры. Пока YoY растёт, цикл продолжается. Исторически разворот YoY вниз при высоких абсолютных значениях совпадал с пиком для полупроводников. Смотрите также на разрыв между capex и ростом выручки этих же компаний: он показывает, сколько стройки финансируется авансом.",
      caveat: "Кварталы по календарной дате окончания, у Oracle финансовый год смещён. Amazon отчитывает покупку основных средств другим тегом. Последний квартал показан, только когда отчитались минимум три компании.",
      src: "SEC EDGAR XBRL companyconcept API",
    },
    {
      id: "equity", section: "supply", kind: "lines", title: "Акции: год назад = 100", unit: "индекс",
      what: "Динамика NVDA, ETF полупроводников SMH, индекса SPY, TSM, Micron, CoreWeave и Oracle, приведённая к 100 на дату год назад.",
      read: "Рынок сам по себе опережающий индикатор. NVDA и SMH, отстающие от SPY при растущем capex, означают сомнения рынка в окупаемости. CoreWeave и Oracle это прокси риска долговой нагрузки AI-инфраструктуры: их падение при стабильном NVDA означает, что рынок боится за финансирование, а не за спрос.",
      caveat: "Цены скорректированы на дивиденды и сплиты. Последняя точка может быть внутридневной.",
      src: "Yahoo Finance chart API",
    },
    {
      id: "credit", section: "supply", kind: "lines", title: "Кредитный спред High Yield", unit: "ICE BofA US HY OAS, %",
      what: "Спред доходности американских высокодоходных облигаций к казначейским.",
      read: "Стройка дата-центров финансируется долгом: CoreWeave, Oracle, проектное финансирование. Расширение спреда означает, что деньги дорожают, и первые трещины в AI-цикле появятся именно здесь, у закредитованных neocloud. Ниже 3 процентов рынок спокоен, выше 5 стресс.",
      caveat: "Общий спред по всему рынку, не только по AI-эмитентам.",
      src: "FRED BAMLH0A0HYM2",
    },
    {
      id: "gas", section: "supply", kind: "lines", title: "Газ Henry Hub", unit: "$/MMBtu",
      what: "Спотовая цена природного газа в США.",
      read: "Электричество для дата-центров в США во многом газовое. Рост цены газа означает рост операционных затрат инференса и ограничения на строительство новых мощностей. Вспомогательный индикатор, важнее для сроков ввода дата-центров, чем для спроса на GPU.",
      caveat: "Не учитывает региональные цены на мощность (PJM, ERCOT), которые для дата-центров важнее.",
      src: "FRED DHHNGSP",
    },

    // ---- Adoption
    {
      id: "pypi", section: "adoption", kind: "lines", log: true, title: "PyPI: скачивания SDK", unit: "в день, среднее за 7 дней, лог-шкала",
      what: "Скачивания Python-пакетов openai, anthropic, litellm, google-genai, langchain и mcp без учёта зеркал.",
      read: "Ежедневный прокси того, сколько кода вызывает модели. Рост означает расширение использования, которое должно компенсировать падение цен на токены. Соотношение anthropic к openai показывает смену предпочтений разработчиков, mcp показывает рост агентной инфраструктуры.",
      caveat: "CI-системы и контейнеры раздувают цифры, важен тренд, а не уровень. История 180 дней.",
      src: "pypistats.org",
    },
    {
      id: "npm", section: "adoption", kind: "lines", log: true, title: "npm: скачивания SDK", unit: "в день, среднее за 7 дней, лог-шкала",
      what: "Скачивания JavaScript-пакетов openai, @anthropic-ai/sdk, ai (Vercel AI SDK), @google/genai и @modelcontextprotocol/sdk.",
      read: "То же, что PyPI, но для веб-разработки, где строится большинство пользовательских AI-продуктов. Расхождение между npm и PyPI показывает, где растёт использование: в продуктах или в исследованиях и бэкендах.",
      caveat: "Те же искажения от CI. История 365 дней.",
      src: "api.npmjs.org",
    },
  ];

  const TILE_UNITS = {
    usd_h: (v) => "$" + v.toFixed(2) + "/ч",
    x: (v) => v.toFixed(2) + "×",
    usd_mtok: (v) => "$" + (v >= 10 ? v.toFixed(1) : v.toFixed(2)) + " /1M",
    pct: (v) => v.toFixed(2) + "%",
    usd_b: (v) => "$" + v.toFixed(0) + " млрд",
    usd: (v) => "$" + v.toFixed(2),
    count: (v) => compact(v),
  };

  function compact(v) {
    if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(0) + "k";
    return String(Math.round(v));
  }
  function fmtNum(v, unitHint) {
    if (v == null || isNaN(v)) return "–";
    if (unitHint && unitHint.indexOf("$/1M") >= 0) return "$" + (v >= 10 ? v.toFixed(1) : v.toFixed(2));
    if (unitHint && unitHint.indexOf("$/GPU") >= 0) return "$" + v.toFixed(2);
    if (Math.abs(v) >= 1e5) return compact(v);
    if (Math.abs(v) >= 100) return v.toFixed(0);
    if (Math.abs(v) >= 10) return v.toFixed(1);
    return v.toFixed(2);
  }
  function signed(p) {
    if (p == null || isNaN(p)) return "";
    return (p > 0 ? "+" : "") + p.toFixed(1) + "%";
  }

  // ------------------------------------------------------------ theme
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function theme() {
    const series = [];
    for (let i = 1; i <= 8; i++) series.push(cssVar("--series-" + i));
    return {
      series,
      text: cssVar("--text"),
      text2: cssVar("--text-2"),
      grid: cssVar("--grid"),
      surface: cssVar("--surface"),
      border: cssVar("--border"),
    };
  }

  function baseLayout(t, card) {
    return {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: t.text2, size: 12, family: "-apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif" },
      margin: { l: 52, r: 12, t: 10, b: 40 },
      hovermode: "x unified",
      hoverlabel: { bgcolor: t.surface, bordercolor: t.border, font: { color: t.text, size: 12 } },
      legend: { orientation: "h", x: 0, y: 1.12, font: { size: 12 }, itemwidth: 30 },
      xaxis: { gridcolor: t.grid, zeroline: false, linecolor: t.grid, tickfont: { size: 11 }, showspikes: false },
      yaxis: {
        gridcolor: t.grid, zeroline: false, linecolor: t.grid, tickfont: { size: 11 },
        type: card.log ? "log" : "linear", rangemode: card.log ? "normal" : "tozero",
        fixedrange: true,
      },
      showlegend: true,
    };
  }
  const CONFIG = { displayModeBar: false, responsive: true, scrollZoom: false };

  // ------------------------------------------------------------ renderers
  function renderLines(el, card, data, t) {
    const traces = data.lines.filter((l) => l.x && l.x.length).map((l, i) => {
      const single = l.x.length <= 3;
      return {
        type: "scatter",
        mode: single ? "markers" : "lines",
        name: l.name,
        x: l.x,
        y: l.y,
        text: l.text,
        line: { width: 2, color: t.series[i % 8], shape: card.step ? "hv" : "linear" },
        marker: { size: 9, color: t.series[i % 8], line: { width: 2, color: t.surface } },
        hovertemplate: "%{y:.4~g}" + (l.text ? " · %{text}" : "") + "<extra>" + l.name + "</extra>",
      };
    });
    const layout = baseLayout(t, card);
    if (traces.length === 1) layout.showlegend = false;
    Plotly.react(el, traces, layout, CONFIG);
  }

  function renderBars(el, card, data, t) {
    const b = data.bars;
    const trace = {
      type: "bar", x: b.x, y: b.y, name: card.title,
      marker: { color: t.series[0] },
      customdata: b.yoy.map((v) => (v == null ? "–" : (v > 0 ? "+" : "") + v.toFixed(1) + "%")),
      hovertemplate: "%{y:.1f} млрд · YoY %{customdata}<extra></extra>",
    };
    const layout = baseLayout(t, card);
    layout.showlegend = false;
    layout.bargap = 0.25;
    Plotly.react(el, [trace], layout, CONFIG);
  }

  function renderBarsLines(el, card, data, t) {
    const traces = data.lines.map((l, i) => ({
      type: "bar", name: l.name, x: l.x, y: l.y, marker: { color: t.series[i] },
      hovertemplate: "%{y}<extra>" + l.name + "</extra>",
    }));
    const layout = baseLayout(t, card);
    layout.barmode = "group";
    layout.bargap = 0.2;
    Plotly.react(el, traces, layout, CONFIG);
  }

  function renderGrouped(el, card, data, t) {
    const traces = data.bars.map((b, i) => ({
      type: "bar", name: b.name, x: data.categories, y: b.y, marker: { color: t.series[i] },
      text: b.y.map((v) => (v == null ? "" : "$" + v.toFixed(2))), textposition: "outside", textfont: { size: 11, color: t.text2 },
      hovertemplate: "$%{y:.2f}<extra>" + b.name + "</extra>",
    }));
    const layout = baseLayout(t, card);
    layout.barmode = "group";
    layout.hovermode = "closest";
    layout.yaxis.range = [0, Math.max(...data.bars.flatMap((b) => b.y.filter((v) => v != null))) * 1.2];
    Plotly.react(el, traces, layout, CONFIG);
  }

  function renderStacked(el, card, data, t) {
    const traces = data.lines.map((l, i) => ({
      type: "bar", name: l.name, x: l.x, y: l.y, marker: { color: t.series[i] },
      hovertemplate: "%{y:.1f}<extra>" + l.name + "</extra>",
    }));
    const tot = data.total;
    traces.push({
      type: "scatter", mode: "lines", name: "Сумма", x: tot.x, y: tot.y,
      line: { width: 0, color: t.text2 }, showlegend: false,
      customdata: tot.yoy.map((v) => (v == null ? "–" : (v > 0 ? "+" : "") + v.toFixed(0) + "%")),
      hovertemplate: "Σ %{y:.0f} млрд · YoY %{customdata}<extra></extra>",
    });
    const layout = baseLayout(t, card);
    layout.barmode = "stack";
    layout.bargap = 0.25;
    Plotly.react(el, traces, layout, CONFIG);
  }

  function renderTable(el, card, data) {
    const rows = data.rows.slice().sort((a, b) => b.providers - a.providers);
    let h = '<div class="tablewrap"><table><thead><tr><th>Модель</th><th class="num">Провайдеров</th><th class="num">Мин. output</th><th class="num">Медиана</th><th class="num">Цена вендора</th></tr></thead><tbody>';
    for (const r of rows) {
      h += "<tr><td>" + r.model + '</td><td class="num">' + r.providers + '</td><td class="num">' + fmtMtok(r.min_output) + '</td><td class="num">' + fmtMtok(r.median_output) + '</td><td class="num">' + (r.fp_output == null ? '<span class="muted">не хостит</span>' : fmtMtok(r.fp_output)) + "</td></tr>";
    }
    h += "</tbody></table></div>";
    el.innerHTML = h;
  }
  function fmtMtok(v) {
    return v == null ? "–" : "$" + (v >= 10 ? v.toFixed(1) : v.toFixed(2));
  }

  function renderEvents(el, card, data) {
    let h = '<div class="tablewrap"><table><thead><tr><th>Неделя</th><th>Вендор</th><th>Модель</th><th>Токены</th><th class="num">Было</th><th class="num">Стало</th><th class="num">Изм.</th></tr></thead><tbody>';
    for (const e of data.rows) {
      const cls = e.pct < 0 ? "down" : "up";
      h += "<tr><td>" + e.date + "</td><td>" + e.vendor + "</td><td>" + e.model + "</td><td>" + (e.metric === "input" ? "input" : "output") + '</td><td class="num">' + fmtMtok(e.old) + '</td><td class="num">' + fmtMtok(e.new) + '</td><td class="num ' + cls + '">' + signed(e.pct) + "</td></tr>";
    }
    h += "</tbody></table></div>";
    el.innerHTML = h;
  }

  // ------------------------------------------------------------ cards
  function latestText(card, data) {
    if (data.lines && data.lines.length && data.lines[0].x.length) {
      const l = data.lines[0];
      const n = l.x.length - 1;
      return l.name + ": " + fmtNum(l.y[n], card.unit) + " · " + l.x[n];
    }
    if (data.bars && data.bars.x && data.bars.x.length) {
      const n = data.bars.x.length - 1;
      const yoy = data.bars.yoy[n];
      return data.bars.x[n] + ": " + fmtNum(data.bars.y[n]) + (yoy == null ? "" : " · YoY " + signed(yoy));
    }
    if (data.total && data.total.x.length) {
      const n = data.total.x.length - 1;
      return data.total.x[n] + ": Σ $" + data.total.y[n].toFixed(0) + " млрд · YoY " + signed(data.total.yoy[n]);
    }
    if (data.rows) return data.rows.length + " строк";
    return "";
  }

  function buildCard(card, data) {
    const wrap = document.createElement("article");
    wrap.className = "card" + (card.wide ? " wide" : "");
    wrap.id = "card-" + card.id;
    const empty = !data || ((data.lines && !data.lines.some((l) => l.x && l.x.length)) || (data.bars && data.bars.x && !data.bars.x.length) || (data.rows && !data.rows.length));
    wrap.innerHTML =
      "<h3>" + card.title + '<span class="unit">' + card.unit + "</span></h3>" +
      '<div class="latest">' + (empty ? "нет данных, источник недоступен на момент сборки" : latestText(card, data)) + "</div>" +
      '<div class="chart' + (card.kind === "table" || card.kind === "events" ? " auto" : "") + '"></div>' +
      '<div class="explain"><p><b>Что это.</b> ' + card.what + "</p><p><b>Как читать.</b> " + card.read + "</p>" +
      (card.caveat ? "<p><b>Оговорка.</b> " + card.caveat + "</p>" : "") +
      '<p class="src">Источник: ' + card.src + "</p></div>";
    document.getElementById("cards-" + card.section).appendChild(wrap);
    return { el: wrap.querySelector(".chart"), empty };
  }

  function draw(card, data, el, t) {
    switch (card.kind) {
      case "lines": return renderLines(el, card, data, t);
      case "bars": return renderBars(el, card, data, t);
      case "bars_lines": return renderBarsLines(el, card, data, t);
      case "grouped": return renderGrouped(el, card, data, t);
      case "stacked": return renderStacked(el, card, data, t);
      case "table": return renderTable(el, card, data);
      case "events": return renderEvents(el, card, data);
    }
  }

  function renderTiles(tiles) {
    const root = document.getElementById("tiles");
    root.innerHTML = "";
    for (const tl of tiles) {
      if (tl.value == null) continue;
      const f = TILE_UNITS[tl.unit] || ((v) => fmtNum(v));
      const d = tl.delta_pct;
      const cls = d == null ? "" : d < 0 ? "down" : "up";
      const dl = d == null ? "" : signed(d) + (tl.delta_days ? " за " + (tl.delta_days >= 365 ? "год" : tl.delta_days + "д") : "");
      const div = document.createElement("div");
      div.className = "tile";
      div.innerHTML = '<div class="label">' + tl.label + '</div><div class="value">' + f(tl.value) + '</div><div class="delta ' + cls + '">' + dl + '</div><div class="note">' + (tl.note ? tl.note + " · " : "") + (tl.date || "") + "</div>";
      root.appendChild(div);
    }
  }

  // ------------------------------------------------------------ theme toggle (?theme=light|dark, remembered per browser)
  function applyTheme(mode) {
    if (mode === "light" || mode === "dark") document.documentElement.setAttribute("data-theme", mode);
    else document.documentElement.removeAttribute("data-theme");
    try { if (mode) localStorage.setItem("theme", mode); else localStorage.removeItem("theme"); } catch (e) { /* storage may be unavailable */ }
    const b = document.getElementById("theme-toggle");
    if (b) b.textContent = currentIsDark() ? "светлая тема" : "тёмная тема";
  }
  function currentIsDark() {
    const forced = document.documentElement.getAttribute("data-theme");
    if (forced) return forced === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  (function initTheme() {
    let mode = new URLSearchParams(location.search).get("theme");
    if (!mode) { try { mode = localStorage.getItem("theme"); } catch (e) { mode = null; } }
    applyTheme(mode || null);
  })();

  // ------------------------------------------------------------ main
  let STATE = null;
  function renderAll() {
    const t = theme();
    for (const c of STATE.cards) if (!c.empty) draw(c.card, c.data, c.el, t);
  }

  fetch("data/dashboard.json?v=" + Date.now())
    .then((r) => r.json())
    .then((dash) => {
      document.getElementById("generated").textContent = dash.generated.replace("T", " ").slice(0, 16) + " UTC";
      document.getElementById("rows").textContent = dash.rows.toLocaleString("ru-RU");
      renderTiles(dash.tiles);
      STATE = { cards: [] };
      for (const card of CARDS) {
        const data = dash.indicators[card.id] || {};
        const { el, empty } = buildCard(card, data);
        STATE.cards.push({ card, data, el, empty });
      }
      if (dash.status && dash.status.failed && dash.status.failed.length) {
        document.getElementById("status").textContent = "Последний сбор " + dash.status.date + ": не ответили источники " + dash.status.failed.join(", ") + ". Показаны предыдущие данные.";
      }
      renderAll();
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq.addEventListener) mq.addEventListener("change", () => { applyTheme(document.documentElement.getAttribute("data-theme")); renderAll(); });
      const tb = document.getElementById("theme-toggle");
      if (tb) {
        tb.textContent = currentIsDark() ? "светлая тема" : "тёмная тема";
        tb.addEventListener("click", () => { applyTheme(currentIsDark() ? "light" : "dark"); renderAll(); });
      }
    })
    .catch((e) => {
      document.getElementById("tiles").innerHTML = '<p class="muted">Не удалось загрузить data/dashboard.json: ' + e + "</p>";
    });
})();
