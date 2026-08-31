import { SCENARIOS } from "./config.js";

const ink = "#241a14";
const muted = "#6d6259";
const rule = "#ded5ca";
const paper = "#fbf8f2";

function baseText() {
  return {
    color: ink,
    fontFamily: "Inter Variable, Inter, Segoe UI, sans-serif",
  };
}

export function comparisonChartOption(rows, currency, fxRate) {
  const mapped = SCENARIOS.map((scenario) => ({
    scenario,
    row: rows.find((item) => item.scenario_id === scenario.id),
  })).filter((item) => item.row);

  const lcoeFactor = currency === "PKR" ? fxRate : 1;
  const labels = mapped.map(({ scenario }) => scenario.shortName);
  const generationSeries = [];
  const lcoeSeries = [];

  mapped.forEach(({ scenario, row }) => {
    generationSeries.push(
      {
        name: `${scenario.name} range`,
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: [
          [row.p90_generation_mwh, scenario.shortName],
          [row.p10_generation_mwh, scenario.shortName],
        ],
        symbol: "none",
        lineStyle: { width: 1.5, color: scenario.color },
        emphasis: { disabled: true },
        tooltip: { show: false },
      },
      {
        name: scenario.name,
        type: "scatter",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: [[row.p50_generation_mwh, scenario.shortName]],
        symbolSize: 11,
        itemStyle: { color: scenario.color },
      },
    );
    lcoeSeries.push({
      name: `${scenario.name} LCOE`,
      type: "scatter",
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: [[row.lcoe_usd_per_mwh * lcoeFactor, scenario.shortName]],
      symbolSize: 11,
      itemStyle: { color: scenario.color },
    });
  });

  return {
    animationDuration: 450,
    backgroundColor: "transparent",
    textStyle: baseText(),
    tooltip: {
      trigger: "item",
      borderColor: rule,
      backgroundColor: "#fffdf9",
      textStyle: { color: ink, fontSize: 12 },
      formatter: (params) => {
        const value = Number(params.value[0]);
        const unit = params.seriesName.includes("LCOE")
          ? `${currency}/MWh`
          : "MWh";
        return `${params.seriesName}<br/><strong>${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}</strong>`;
      },
    },
    grid: [
      { left: 56, top: 54, width: "39%", bottom: 26, containLabel: true },
      { right: 16, top: 54, width: "39%", bottom: 26, containLabel: true },
    ],
    title: [
      {
        text: "P50 generation (MWh)",
        subtext: "with P90–P10 range",
        left: 56,
        top: 4,
        textStyle: { color: ink, fontSize: 12, fontWeight: 650 },
        subtextStyle: { color: muted, fontSize: 10 },
      },
      {
        text: `LCOE (${currency}/MWh)`,
        subtext: "P50",
        left: "53%",
        top: 4,
        textStyle: { color: ink, fontSize: 12, fontWeight: 650 },
        subtextStyle: { color: muted, fontSize: 10 },
      },
    ],
    xAxis: [
      {
        type: "value",
        gridIndex: 0,
        min: 0,
        max: 420000,
        position: "top",
        axisLabel: { color: muted, fontSize: 10, formatter: (v) => (v === 0 ? "0" : `${v / 1000}k`) },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: rule } },
      },
      {
        type: "value",
        gridIndex: 1,
        min: 0,
        max: currency === "PKR" ? 650000 : 2200,
        position: "top",
        axisLabel: { color: muted, fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: rule } },
      },
    ],
    yAxis: [0, 1].map((gridIndex) => ({
      type: "category",
      gridIndex,
      data: labels,
      inverse: true,
      axisLabel: { color: ink, fontSize: 11, margin: 12 },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
    })),
    series: [...generationSeries, ...lcoeSeries],
  };
}

export function sensitivityChartOption(points, frontier, currency, fxRate) {
  const factor = currency === "PKR" ? fxRate : 1;
  const capexValues = [...new Set(points.map((point) => point.x_value))].sort((a, b) => a - b);
  const priceValues = [...new Set(points.map((point) => point.y_value * factor))].sort((a, b) => a - b);
  const capexCategories = capexValues.map(String);
  const priceCategories = priceValues.map((value) => String(value));
  const converted = points.map((point) => [
    String(point.x_value),
    String(point.y_value * factor),
    point.metric_value == null ? null : point.metric_value * factor,
  ]);
  const convertedFrontier = frontier.map(([capex, price]) => [String(capex), price * factor]);

  return {
    animationDuration: 450,
    textStyle: baseText(),
    tooltip: {
      position: "top",
      borderColor: rule,
      backgroundColor: "#fffdf9",
      textStyle: { color: ink, fontSize: 12 },
      formatter: (params) => {
        if (params.seriesType === "line") return `Break-even<br/><strong>${currency} ${Number(params.value[1]).toLocaleString(undefined, { maximumFractionDigits: 1 })}/MWh</strong>`;
        const [capex, price, lcoe] = params.value;
        return `CAPEX ${currency === "PKR" ? "USD" : "USD"} ${capex.toLocaleString()}/kW<br/>Price ${currency} ${price.toLocaleString(undefined, { maximumFractionDigits: 1 })}/MWh<br/><strong>LCOE ${currency} ${lcoe.toLocaleString(undefined, { maximumFractionDigits: 1 })}/MWh</strong>`;
      },
    },
    grid: { left: 70, right: 90, top: 24, bottom: 42 },
    xAxis: {
      type: "category",
      data: capexCategories,
      name: "CAPEX (USD/kW)",
      nameLocation: "middle",
      nameGap: 30,
      axisLabel: { color: muted, fontSize: 10 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: "rgba(255,255,255,.48)" } },
    },
    yAxis: [
      {
        type: "category",
        data: priceCategories,
        name: `Electricity price (${currency}/MWh)`,
        nameLocation: "middle",
        nameGap: 48,
        axisLabel: { color: muted, fontSize: 10 },
        axisLine: { lineStyle: { color: rule } },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "rgba(255,255,255,.48)" } },
      },
      {
        type: "value",
        min: 30 * factor,
        max: 130 * factor,
        show: false,
      },
    ],
    visualMap: {
      type: "piecewise",
      seriesIndex: 0,
      orient: "vertical",
      right: 0,
      top: 12,
      textStyle: { color: muted, fontSize: 9 },
      pieces: [
        { lt: 40 * factor, label: "< 40", color: "#f6e3aa" },
        { gte: 40 * factor, lt: 60 * factor, label: "40–60", color: "#efbf55" },
        { gte: 60 * factor, lt: 80 * factor, label: "60–80", color: "#d88327" },
        { gte: 80 * factor, lt: 100 * factor, label: "80–100", color: "#a94a20" },
        { gte: 100 * factor, lt: 120 * factor, label: "100–120", color: "#71311d" },
        { gte: 120 * factor, label: "> 120", color: "#391d10" },
      ],
    },
    series: [
      {
        name: "LCOE",
        type: "heatmap",
        yAxisIndex: 0,
        data: converted,
        itemStyle: { borderWidth: 1, borderColor: "rgba(255,255,255,.36)" },
        emphasis: { itemStyle: { borderColor: paper, borderWidth: 2 } },
      },
      {
        name: "Break-even frontier (LCOE = price)",
        type: "line",
        yAxisIndex: 1,
        data: convertedFrontier,
        showSymbol: false,
        smooth: 0.18,
        lineStyle: { color: "#fffdf9", width: 2.5, type: "dotted" },
        z: 5,
      },
    ],
  };
}

export function annualGenerationOption(annualGeneration, statistics, color) {
  const years = annualGeneration.map((item) => String(item.year));
  return {
    animationDuration: 450,
    textStyle: baseText(),
    tooltip: {
      trigger: "axis",
      borderColor: rule,
      backgroundColor: "#fffdf9",
      textStyle: { color: ink, fontSize: 11 },
    },
    grid: { left: 58, right: 54, top: 28, bottom: 42 },
    legend: { right: 0, top: 0, textStyle: { color: muted, fontSize: 10 } },
    xAxis: {
      type: "category",
      data: years,
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false },
      axisLabel: { color: muted, fontSize: 10 },
    },
    yAxis: [
      {
        type: "value",
        name: "Generation (MWh)",
        nameTextStyle: { color: muted, fontSize: 10 },
        axisLabel: { color: muted, fontSize: 9, formatter: (value) => `${Math.round(value / 1000)}k` },
        splitLine: { lineStyle: { color: rule } },
      },
      {
        type: "value",
        name: "Capacity factor",
        nameTextStyle: { color: muted, fontSize: 10 },
        axisLabel: { color: muted, fontSize: 9, formatter: (value) => `${Math.round(value * 100)}%` },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "Annual generation",
        type: "bar",
        data: annualGeneration.map((item) => item.generation_mwh),
        barMaxWidth: 34,
        itemStyle: { color, borderRadius: [2, 2, 0, 0] },
        markLine: {
          symbol: "none",
          silent: true,
          label: { color: muted, fontSize: 9, formatter: "P50" },
          lineStyle: { color: "#71311d", type: "dashed", width: 1.5 },
          data: statistics?.p50_mwh ? [{ yAxis: statistics.p50_mwh }] : [],
        },
      },
      {
        name: "Capacity factor",
        type: "line",
        yAxisIndex: 1,
        data: annualGeneration.map((item) => item.capacity_factor),
        showSymbol: true,
        symbolSize: 5,
        lineStyle: { color: "#2b190e", width: 1.6 },
        itemStyle: { color: "#2b190e" },
      },
    ],
  };
}

export function economicsOverviewOption(evaluation, currency, fxRate) {
  const factor = currency === "PKR" ? fxRate : 1;
  const million = 1_000_000;
  const values = [
    evaluation.initial_capex_usd,
    evaluation.lifetime_revenue_usd,
    evaluation.lifetime_opex_usd,
    evaluation.npv_usd,
  ].map((value) => (Number(value) * factor) / million);
  return {
    animationDuration: 450,
    textStyle: baseText(),
    tooltip: {
      trigger: "axis",
      borderColor: rule,
      backgroundColor: "#fffdf9",
      textStyle: { color: ink, fontSize: 11 },
      valueFormatter: (value) => `${currency} ${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })}m`,
    },
    grid: { left: 62, right: 18, top: 20, bottom: 38 },
    xAxis: {
      type: "category",
      data: ["Initial\nCAPEX", "Lifetime\nrevenue", "Lifetime\nOPEX", "NPV"],
      axisLabel: { color: muted, fontSize: 10, interval: 0 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      name: `${currency}, million`,
      nameTextStyle: { color: muted, fontSize: 10 },
      axisLabel: { color: muted, fontSize: 9 },
      splitLine: { lineStyle: { color: rule } },
    },
    series: [{
      type: "bar",
      data: values.map((value, index) => ({
        value,
        itemStyle: { color: index === 3 && value < 0 ? "#9b3c20" : ["#71311d", "#c78a2a", "#bd4b1e", "#526249"][index] },
      })),
      barMaxWidth: 54,
    }],
  };
}

export function oneWaySensitivityOption(result, xLabel, metricLabel) {
  const points = result?.points || [];
  return {
    animationDuration: 450,
    textStyle: baseText(),
    tooltip: {
      trigger: "axis",
      borderColor: rule,
      backgroundColor: "#fffdf9",
      textStyle: { color: ink, fontSize: 11 },
    },
    grid: { left: 68, right: 20, top: 22, bottom: 48 },
    xAxis: {
      type: "value",
      name: xLabel,
      nameLocation: "middle",
      nameGap: 32,
      axisLabel: { color: muted, fontSize: 9 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule } },
    },
    yAxis: {
      type: "value",
      name: metricLabel,
      nameTextStyle: { color: muted, fontSize: 10 },
      axisLabel: { color: muted, fontSize: 9 },
      splitLine: { lineStyle: { color: rule } },
    },
    series: [{
      type: "line",
      data: points.filter((point) => point.metric_value != null).map((point) => [point.parameter_value, point.metric_value]),
      showSymbol: true,
      symbolSize: 7,
      smooth: 0.16,
      lineStyle: { color: "#71311d", width: 2.2 },
      itemStyle: { color: "#bd4b1e" },
      areaStyle: { color: "rgba(199,138,42,.14)" },
      markPoint: result?.baseline_parameter_value == null ? undefined : {
        symbolSize: 42,
        label: { color: "#fff", fontSize: 9, formatter: "Base" },
        itemStyle: { color: "#2b190e" },
        data: [{
          coord: [result.baseline_parameter_value, result.baseline_metric_value],
          value: result.baseline_metric_value,
        }],
      },
    }],
  };
}

export function waveCompetitivenessOption(result) {
  const points = result?.points || [];
  const xCategories = (result?.x_values || []).map(String);
  const yCategories = (result?.y_values || []).map((value) => String(value));
  const benchmark = Number(result?.benchmark_value);
  const hasBenchmark = Number.isFinite(benchmark) && benchmark > 0;
  const heatmapData = points.map((point) => {
    const metricValue = Number(point.metric_value);
    const multiple = hasBenchmark && Number.isFinite(metricValue) ? metricValue / benchmark : null;
    return [String(point.x_value), String(point.y_value), point.metric_value, point.is_competitive, multiple];
  });
  const baselineX = String(result?.baseline_x_value);
  const baselineY = String(result?.baseline_y_value);
  const hasBaseline = xCategories.includes(baselineX) && yCategories.includes(baselineY);
  return {
    animationDuration: 450,
    textStyle: baseText(),
    aria: {
      enabled: true,
      description: "Heatmap of wave LCOE relative to the Solar benchmark across CAPEX and conversion efficiency. The current wave case is marked when it falls on the tested grid.",
    },
    tooltip: {
      position: "top",
      borderColor: rule,
      backgroundColor: "#fffdf9",
      textStyle: { color: ink, fontSize: 11 },
      formatter: (params) => {
        if (params.seriesName === "Current wave case") {
          return `Current wave case<br/>CAPEX USD ${Number(params.value[0]).toLocaleString()}/kW<br/>Efficiency ${(Number(params.value[1]) * 100).toFixed(1)}%<br/><strong>LCOE USD ${Number(result?.baseline_metric_value).toLocaleString(undefined, { maximumFractionDigits: 1 })}/MWh</strong>`;
        }
        if (params.seriesType === "line") return `Competitive boundary<br/><strong>${Number(params.value[1] * 100).toFixed(1)}% efficiency at USD ${Number(params.value[0]).toLocaleString()}/kW</strong>`;
        const [capex, efficiency, lcoe, competitive, multiple] = params.value;
        const comparison = Number.isFinite(multiple) ? `${Number(multiple).toFixed(multiple >= 10 ? 0 : 1)}× the Solar benchmark` : "Benchmark unavailable";
        return `CAPEX USD ${Number(capex).toLocaleString()}/kW<br/>Efficiency ${(Number(efficiency) * 100).toFixed(1)}%<br/><strong>LCOE USD ${Number(lcoe).toLocaleString(undefined, { maximumFractionDigits: 1 })}/MWh</strong><br/>${comparison}<br/>${competitive ? "At or below benchmark" : "Above benchmark"}`;
      },
    },
    legend: {
      show: hasBaseline || (result?.frontier || []).length > 0,
      top: 0,
      left: 8,
      itemWidth: 14,
      itemHeight: 7,
      textStyle: { color: muted, fontSize: 9 },
    },
    grid: { left: 78, right: 142, top: 38, bottom: 52 },
    xAxis: {
      type: "category",
      data: xCategories,
      name: "Wave CAPEX (USD/kW)",
      nameLocation: "middle",
      nameGap: 34,
      axisLabel: { color: muted, fontSize: 9, formatter: (value) => Number(value).toLocaleString() },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "category",
      data: yCategories,
      name: "Conversion efficiency",
      nameLocation: "middle",
      nameGap: 52,
      axisLabel: { color: muted, fontSize: 9, formatter: (value) => `${Math.round(Number(value) * 100)}%` },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false },
    },
    visualMap: {
      type: "piecewise",
      dimension: 4,
      orient: "vertical",
      right: 0,
      top: 42,
      selectedMode: false,
      itemWidth: 14,
      itemHeight: 12,
      itemGap: 6,
      textStyle: { color: muted, fontSize: 9 },
      pieces: [
        { lte: 1, label: "At / below Solar", color: "#f5e8b9" },
        { gt: 1, lte: 2, label: "1–2× Solar", color: "#e7bc5f" },
        { gt: 2, lte: 5, label: "2–5× Solar", color: "#cf7c2b" },
        { gt: 5, lte: 10, label: "5–10× Solar", color: "#8f4023" },
        { gt: 10, label: ">10× Solar", color: "#391d10" },
      ],
    },
    series: [
      {
        name: "Wave LCOE",
        type: "heatmap",
        data: heatmapData,
        itemStyle: { borderWidth: 1, borderColor: "rgba(255,255,255,.45)" },
        emphasis: { itemStyle: { borderColor: "#241a14", borderWidth: 2 } },
      },
      {
        name: "Competitive boundary",
        type: "line",
        data: (result?.frontier || []).map(([x, y]) => [String(x), String(y)]),
        showSymbol: true,
        symbolSize: 5,
        lineStyle: { color: "#fffdf9", width: 2.5, type: "dashed" },
        itemStyle: { color: "#fffdf9" },
        z: 5,
      },
      ...(hasBaseline ? [{
        name: "Current wave case",
        type: "scatter",
        data: [[baselineX, baselineY]],
        symbol: "circle",
        symbolSize: 18,
        itemStyle: { color: "#fffdf9", borderColor: "#241a14", borderWidth: 3 },
        label: {
          show: true,
          formatter: "Current",
          position: "top",
          color: "#241a14",
          fontSize: 9,
          fontWeight: 700,
          backgroundColor: "rgba(255,253,249,.9)",
          padding: [3, 5],
          borderRadius: 2,
        },
        z: 8,
      }] : []),
    ],
  };
}

export function riskHistogramOption(samples, field, currency, fxRate) {
  const factor = field === "npv_usd" && currency === "PKR" ? fxRate : 1;
  const values = samples.map((sample) => sample[field]).filter(Number.isFinite).map((value) => value * factor);
  if (!values.length) return { series: [] };
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const binCount = Math.min(16, Math.max(6, Math.round(Math.sqrt(values.length))));
  const width = maximum === minimum ? 1 : (maximum - minimum) / binCount;
  const bins = Array.from({ length: binCount }, (_, index) => ({
    lower: minimum + index * width,
    upper: minimum + (index + 1) * width,
    count: 0,
  }));
  values.forEach((value) => {
    const index = Math.min(binCount - 1, Math.floor((value - minimum) / width));
    bins[index].count += 1;
  });
  return {
    animationDuration: 450,
    textStyle: baseText(),
    tooltip: {
      trigger: "axis",
      borderColor: rule,
      backgroundColor: "#fffdf9",
      textStyle: { color: ink, fontSize: 11 },
    },
    grid: { left: 50, right: 18, top: 18, bottom: 54 },
    xAxis: {
      type: "category",
      data: bins.map((bin) => ((bin.lower + bin.upper) / 2).toLocaleString(undefined, { maximumFractionDigits: 0 })),
      name: field === "npv_usd" ? `${currency} NPV` : "USD/MWh LCOE",
      nameLocation: "middle",
      nameGap: 36,
      axisLabel: { color: muted, fontSize: 8, rotate: 28 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      name: "Simulations",
      nameTextStyle: { color: muted, fontSize: 9 },
      axisLabel: { color: muted, fontSize: 9 },
      splitLine: { lineStyle: { color: rule } },
    },
    series: [{ type: "bar", data: bins.map((bin) => bin.count), barCategoryGap: "8%", itemStyle: { color: "#71311d" } }],
  };
}
