import { useEffect, useMemo, useRef, useState } from "react";
import ReactECharts from "./EnergyChart.jsx";
import {
  ArrowSquareOut,
  ArrowsClockwise,
  CalendarBlank,
  CaretLeft,
  CaretRight,
  ChartBar,
  CheckCircle,
  BookOpenText,
  CurrencyDollar,
  CurrencyCircleDollar,
  Database,
  DownloadSimple,
  FileText,
  Gear,
  Info,
  House,
  MapPin,
  MapTrifold,
  Play,
  Question,
  SlidersHorizontal,
  SquaresFour,
  Warning,
  X,
} from "@phosphor-icons/react";
import "@fontsource-variable/inter";

import {
  INITIAL_MARKET_CONTEXT,
  PAKISTAN_COORDINATE_BOUNDS,
  PROJECT_DATE,
  SCENARIOS,
  buildAnalysisRequest,
  fallbackRows,
  scenarioInputsFromDefaults,
} from "./config.js";
import { comparisonChartOption, sensitivityChartOption } from "./charts.js";
import {
  BuildPage,
  EconomicsPage,
  HomePage,
  MethodologyPage,
  ResourcePage,
  RiskPage,
  SensitivityPage,
  SourcesPage,
} from "./WorkspacePages.jsx";

const navItems = [
  { id: "overview", label: "Overview", icon: House },
  { id: "build", label: "New analysis", icon: SquaresFour },
  { id: "resource", label: "Resource", icon: MapTrifold },
  { id: "economics", label: "Economics", icon: CurrencyCircleDollar },
  { id: "compare", label: "Compare", icon: ChartBar },
  { id: "sensitivity", label: "Sensitivity", icon: SlidersHorizontal },
  { id: "risk", label: "Risk", icon: Warning },
  { id: "methodology", label: "Methodology", icon: BookOpenText },
  { id: "sources", label: "Sources", icon: FileText },
];

const cautionItems = [
  {
    title: "Wave period proxy used",
    body: "No in-situ wave buoys; ERA5-Ocean wave period is used as an energy-period proxy. LCOE remains highly uncertain.",
  },
  {
    title: "Missing bathymetry",
    body: "Site-specific water depth is unavailable, so the deep-water assumption cannot yet be checked.",
  },
  {
    title: "Reference wind curve",
    body: "The default uses the tabulated NLR/IEA 3.4 MW reference curve; final engineering still needs the selected turbine's certified site-specific curve.",
  },
];

const pageMeta = {
  build: { title: "New analysis", subtitle: "Configure Solar, Wind, and Wave together at any Pakistan coordinates" },
  resource: { title: "Resource", subtitle: "Historical record, annual generation and data quality" },
  economics: { title: "Economics", subtitle: "Unlevered project value, cost and return" },
  compare: { title: "Scenario comparison", subtitle: "P50 · controlled technology comparison" },
  sensitivity: { title: "Sensitivity & break-even", subtitle: "Test drivers and solve competitiveness thresholds" },
  risk: { title: "Advanced risk", subtitle: "Joint economic worlds, paired probabilities and standalone distributions" },
  methodology: { title: "Methodology", subtitle: "Equations, dependency scopes and model boundaries" },
  sources: { title: "Sources & assumptions", subtitle: "Provider metadata, current cost basis and evidence register" },
};

function comparisonRowFromAnalysis(analysis, request) {
  const evaluation = analysis.evaluations.p50;
  const statistics = analysis.generation_statistics;
  return {
    scenario_id: analysis.scenario_id,
    technology: analysis.technology,
    location_name: request.location.name,
    requested_latitude: analysis.resource.requested_latitude,
    requested_longitude: analysis.resource.requested_longitude,
    resolved_latitude: analysis.resource.resolved_latitude,
    resolved_longitude: analysis.resource.resolved_longitude,
    resource_source_name: analysis.resource.source_name,
    resource_dataset_name: analysis.resource.dataset_name,
    generation_basis: "p50",
    capacity_mw: request.capacity_mw,
    lifetime_years: request.lifetime_years,
    first_year_generation_mwh: evaluation.first_year_generation_mwh,
    equivalent_capacity_factor: evaluation.equivalent_first_year_capacity_factor,
    lifetime_generation_mwh: evaluation.lifetime_generation_mwh,
    initial_capex_usd: evaluation.initial_capex_usd,
    npv_usd: evaluation.npv_usd,
    project_irr: evaluation.project_irr,
    lcoe_usd_per_mwh: evaluation.lcoe_usd_per_mwh,
    simple_payback_years: evaluation.simple_payback_years,
    discounted_payback_years: evaluation.discounted_payback_years,
    lifetime_revenue_usd: evaluation.lifetime_revenue_usd,
    lifetime_opex_usd: evaluation.lifetime_opex_usd,
    resource_coefficient_of_variation: statistics.coefficient_of_variation,
    p90_generation_mwh: statistics.p90_mwh,
    p50_generation_mwh: statistics.p50_mwh,
    p10_generation_mwh: statistics.p10_mwh,
    resource_spread_fraction: statistics.p50_mwh ? (statistics.p10_mwh - statistics.p90_mwh) / statistics.p50_mwh : null,
  };
}

function linearValues(minimum, maximum, count) {
  const safeCount = Math.max(2, Math.min(101, Math.round(count)));
  const step = (maximum - minimum) / (safeCount - 1);
  return Array.from({ length: safeCount }, (_, index) => minimum + index * step);
}

function cloneInputs(inputs) {
  return Object.fromEntries(
    Object.entries(inputs).map(([key, value]) => [key, { ...value }]),
  );
}

function formatNumber(value, maximumFractionDigits = 0) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits });
}

function formatDateTime(value) {
  if (!value) return "not available";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatCoordinate(value, positiveSuffix, negativeSuffix) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${Math.abs(numeric).toFixed(4)}°${numeric >= 0 ? positiveSuffix : negativeSuffix}`;
}

function validatePakistanSite(inputs) {
  const latitude = Number(inputs.latitude);
  const longitude = Number(inputs.longitude);
  const bounds = PAKISTAN_COORDINATE_BOUNDS;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return "Enter valid numeric coordinates.";
  if (latitude < bounds.minimumLatitude || latitude > bounds.maximumLatitude) {
    return `Latitude must be between ${bounds.minimumLatitude} and ${bounds.maximumLatitude} for Pakistan.`;
  }
  if (longitude < bounds.minimumLongitude || longitude > bounds.maximumLongitude) {
    return `Longitude must be between ${bounds.minimumLongitude} and ${bounds.maximumLongitude} for Pakistan.`;
  }
  return null;
}

async function apiJson(path, body) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Keep the status text when the body is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

function NavButton({ item, active, onClick }) {
  const Icon = item.icon;
  return (
    <button
      type="button"
      className={`nav-button ${active ? "is-active" : ""}`}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
    >
      <Icon size={20} weight={active ? "fill" : "regular"} aria-hidden="true" />
      <span>{item.label}</span>
    </button>
  );
}

function ScenarioSummary({ scenario, scenarioInputs, row, index, selected, onSelect, money }) {
  const irr = row?.project_irr;
  return (
    <article
      className={`scenario-summary ${selected ? "is-selected" : ""}`}
      role="button"
      tabIndex={0}
      aria-label={`Select ${scenario.name}`}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onSelect();
      }}
    >
      <div className="scenario-heading">
        <span className={`scenario-number scenario-${index + 1}`}>{index + 1}</span>
        <div>
          <h2>{scenario.name}</h2>
          <p>{scenario.technologyLabel} <span>·</span> {scenarioInputs?.locationName || scenario.locationLabel}</p>
          <small className="scenario-coordinate">
            <MapPin size={11} weight="fill" aria-hidden="true" />
            {formatCoordinate(scenarioInputs?.latitude, "N", "S")}, {formatCoordinate(scenarioInputs?.longitude, "E", "W")}
          </small>
        </div>
      </div>

      <dl className="scenario-metrics">
        <div>
          <dt>Capacity</dt>
          <dd>{formatNumber(row?.capacity_mw)} MW</dd>
          {scenario.id === "karachi-wave" && <small>research</small>}
        </div>
        <div>
          <dt>P50 generation</dt>
          <dd>{formatNumber(row?.p50_generation_mwh)} MWh</dd>
        </div>
        <div>
          <dt>LCOE (P50)</dt>
          <dd>{money(row?.lcoe_usd_per_mwh, 2)}<small>/MWh</small></dd>
        </div>
        <div>
          <dt>IRR (P50)</dt>
          <dd>{irr == null ? "Undefined" : `${formatNumber(irr * 100, 2)}%`}</dd>
        </div>
      </dl>

      <div className="scenario-foot">
        <span><i style={{ background: scenario.color }} />Evidence: {scenario.evidence}</span>
        <span>Data coverage&nbsp; 2015–2024</span>
      </div>
    </article>
  );
}

function DecisionLens({ rows, money }) {
  const ranked = useMemo(() => {
    const finiteLcoe = rows.filter((row) => Number.isFinite(row.lcoe_usd_per_mwh));
    const finiteIrr = rows.filter((row) => Number.isFinite(row.project_irr));
    const finiteCv = rows.filter((row) => Number.isFinite(row.resource_coefficient_of_variation));
    const byId = (id) => SCENARIOS.find((scenario) => scenario.id === id);
    const lowestLcoe = [...finiteLcoe].sort((a, b) => a.lcoe_usd_per_mwh - b.lcoe_usd_per_mwh)[0];
    const highestIrr = [...finiteIrr].sort((a, b) => b.project_irr - a.project_irr)[0];
    const lowestCv = [...finiteCv].sort((a, b) => a.resource_coefficient_of_variation - b.resource_coefficient_of_variation)[0];
    return [
      {
        label: "Lowest LCOE",
        scenario: byId(lowestLcoe?.scenario_id),
        value: lowestLcoe ? `${money(lowestLcoe.lcoe_usd_per_mwh, 2)} /MWh` : "—",
      },
      {
        label: "Highest IRR",
        scenario: byId(highestIrr?.scenario_id),
        value: highestIrr ? `${formatNumber(highestIrr.project_irr * 100, 2)}%` : "—",
      },
      {
        label: "Lowest resource variability",
        scenario: byId(lowestCv?.scenario_id),
        value: "Lowest P90–P10 spread",
      },
    ];
  }, [rows, money]);

  return (
    <section className="decision-panel" aria-labelledby="decision-title">
      <div className="section-heading compact-heading">
        <div>
          <h2 id="decision-title">Decision lens <Info size={14} weight="bold" /></h2>
          <p>Metric-specific rankings (P50)</p>
        </div>
      </div>
      <ol className="ranking-list">
        {ranked.map((item) => (
          <li key={item.label}>
            <div>
              <span>{item.label}</span>
              <strong>{item.scenario?.name || "Unavailable"}</strong>
              <small>{item.value}</small>
            </div>
            <div className="rank-number"><span>Rank</span><strong>1</strong></div>
          </li>
        ))}
      </ol>
      <div className="no-score-note">
        <Info size={16} weight="bold" aria-hidden="true" />
        <span>No composite score—choose the metric that matches the decision.</span>
      </div>
    </section>
  );
}

function EvidenceRail({ onOpenEvidence, onExport }) {
  return (
    <aside className="evidence-rail" aria-labelledby="evidence-title">
      <h2 id="evidence-title">Evidence & cautions</h2>
      <section>
        <h3>Validation status</h3>
        <div className="evidence-list">
          {SCENARIOS.map((scenario) => (
            <div className="evidence-row" key={scenario.id}>
              <div>
                <strong>{scenario.shortName} resource</strong>
                <span>{scenario.source}</span>
              </div>
              <b>{scenario.evidence}</b>
            </div>
          ))}
        </div>
        <button className="secondary-button full-width" type="button" onClick={onOpenEvidence}>
          View full evidence log <ArrowSquareOut size={15} />
        </button>
      </section>
      <section className="cautions-section">
        <h3>Key cautions</h3>
        <div className="caution-list">
          {cautionItems.map((item) => (
            <article key={item.title}>
              <Warning size={17} weight="bold" aria-hidden="true" />
              <div><strong>{item.title}</strong><p>{item.body}</p></div>
            </article>
          ))}
        </div>
      </section>
      <button className="secondary-button full-width evidence-export" type="button" onClick={onExport}>
        Export evidence pack <DownloadSimple size={15} />
      </button>
    </aside>
  );
}

function ActionRow({ icon: Icon, title, description, onClick }) {
  return (
    <button type="button" className="action-row" onClick={onClick}>
      <Icon size={19} aria-hidden="true" />
      <span><strong>{title}</strong><small>{description}</small></span>
      <CaretRight size={15} weight="bold" aria-hidden="true" />
    </button>
  );
}

function Drawer({ mode, onClose, children, title }) {
  if (!mode) return null;
  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header>
          <h2 id="drawer-title">{title}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close panel">
            <X size={19} />
          </button>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}

export function App() {
  const initialInputs = useMemo(() => scenarioInputsFromDefaults(), []);
  const [inputs, setInputs] = useState(initialInputs);
  const [draftInputs, setDraftInputs] = useState(() => cloneInputs(initialInputs));
  const [rows, setRows] = useState(() => fallbackRows());
  const [sensitivityPoints, setSensitivityPoints] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [market, setMarket] = useState(INITIAL_MARKET_CONTEXT);
  const [assumptionCatalog, setAssumptionCatalog] = useState(null);
  const [currency, setCurrency] = useState("USD");
  const [selectedId, setSelectedId] = useState(SCENARIOS[0].id);
  const [activeNav, setActiveNav] = useState("overview");
  const [drawerMode, setDrawerMode] = useState(null);
  const [runState, setRunState] = useState("idle");
  const [analysisRunState, setAnalysisRunState] = useState("idle");
  const [experimentRunState, setExperimentRunState] = useState("idle");
  const [riskRunState, setRiskRunState] = useState("idle");
  const [analysesById, setAnalysesById] = useState({});
  const [oneWayResults, setOneWayResults] = useState({});
  const [waveResult, setWaveResult] = useState(null);
  const [breakEvenResult, setBreakEvenResult] = useState(null);
  const [riskResults, setRiskResults] = useState({});
  const [jointRiskResult, setJointRiskResult] = useState(null);
  const [statusText, setStatusText] = useState("Validated defaults loaded");
  const [toast, setToast] = useState("");
  const [scenarioFormError, setScenarioFormError] = useState("");
  const started = useRef(false);

  const fxRate = Number(market?.fx?.rate || 1);
  const money = useMemo(() => (value, digits = 0) => {
    if (value == null || !Number.isFinite(Number(value))) return "—";
    const converted = currency === "PKR" ? Number(value) * fxRate : Number(value);
    const prefix = currency === "PKR" ? "PKR " : "$";
    return `${prefix}${formatNumber(converted, digits)}`;
  }, [currency, fxRate]);

  const selectedScenario = SCENARIOS.find((scenario) => scenario.id === selectedId);
  const frontier = useMemo(() => {
    const byCapex = new Map();
    sensitivityPoints.forEach((point) => {
      if (point.metric_value != null && !byCapex.has(point.x_value)) {
        byCapex.set(point.x_value, point.metric_value);
      }
    });
    return [...byCapex.entries()].sort((a, b) => a[0] - b[0]);
  }, [sensitivityPoints]);

  const comparisonOption = useMemo(
    () => comparisonChartOption(rows, currency, fxRate),
    [rows, currency, fxRate],
  );
  const sensitivityOption = useMemo(
    () => sensitivityChartOption(sensitivityPoints, frontier, currency, fxRate),
    [sensitivityPoints, frontier, currency, fxRate],
  );

  function openDrawer(mode) {
    if (mode === "scenarios") {
      setDraftInputs(cloneInputs(inputs));
      setScenarioFormError("");
    }
    setDrawerMode(mode);
  }

  async function runComparison(nextInputs = inputs, quiet = false) {
    setRunState("running");
    setStatusText("Running authoritative model…");
    const analyses = SCENARIOS.map((scenario) =>
      buildAnalysisRequest(scenario, nextInputs[scenario.id]),
    );
    const wind = analyses[0];
    const xValues = [700, 800, 900, 1000, 1100, 1200, 1300, 1400];
    const yValues = [40, 60, 80, 100, 120];

    try {
      const [detailedAnalyses, sensitivity] = await Promise.all([
        Promise.all(analyses.map((analysis) => apiJson("/api/v1/analyses", analysis))),
        apiJson("/api/v1/sensitivity/two-way", {
          analysis: wind,
          x_parameter: "capex_per_kw",
          x_values: xValues,
          y_parameter: "electricity_price_per_mwh",
          y_values: yValues,
          metric: "lcoe",
          generation_basis: "p50",
        }),
      ]);
      setAnalysesById(Object.fromEntries(detailedAnalyses.map((result) => [result.scenario_id, result])));
      setRows(detailedAnalyses.map((result, index) => comparisonRowFromAnalysis(result, analyses[index])));
      setWarnings([...new Set([...detailedAnalyses.flatMap((result) => result.warnings || []), ...(sensitivity.warnings || [])])]);
      setSensitivityPoints(sensitivity.points || []);
      setRunState("success");
      setStatusText("Results current");
      if (!quiet) setToast("Solar, Wind, and Wave completed together.");
      return true;
    } catch (error) {
      setRunState("error");
      setStatusText("Using last validated results");
      setToast(`Model refresh failed: ${error.message}`);
      return false;
    }
  }

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    apiJson("/api/v1/market-context")
      .then(setMarket)
      .catch(() => setMarket(INITIAL_MARKET_CONTEXT));
    apiJson("/api/v1/assumptions")
      .then(setAssumptionCatalog)
      .catch(() => setAssumptionCatalog(null));
    runComparison(inputs, true);
  }, []);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(""), 4200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === "Escape") setDrawerMode(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function handleNav(id) {
    setActiveNav(id);
    if (id === "build") setDraftInputs(cloneInputs(inputs));
    setDrawerMode(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function updateDraft(id, field, value) {
    setScenarioFormError("");
    setDraftInputs((current) => ({
      ...current,
      [id]: { ...current[id], [field]: value },
    }));
  }

  async function applyScenarioChanges() {
    for (const scenario of SCENARIOS) {
      const validationError = validatePakistanSite(draftInputs[scenario.id]);
      if (validationError) {
        setScenarioFormError(`${scenario.name}: ${validationError}`);
        return;
      }
    }
    const normalized = Object.fromEntries(
      Object.entries(draftInputs).map(([id, value]) => [id, {
        ...value,
        latitude: Number(value.latitude),
        longitude: Number(value.longitude),
        locationName: String(value.locationName || "").trim() || `Pakistan site ${Number(value.latitude).toFixed(4)}, ${Number(value.longitude).toFixed(4)}`,
        capex: Math.max(1, Number(value.capex)),
        electricityPrice: Math.max(1, Number(value.electricityPrice)),
      }]),
    );
    setDrawerMode(null);
    const succeeded = await runComparison(normalized);
    if (succeeded) {
      setInputs(normalized);
    } else {
      setDrawerMode("scenarios");
      setScenarioFormError("The new site was not applied because its resource run did not complete. Your entries are still here.");
    }
  }

  async function runAllDraftAnalyses() {
    for (const scenario of SCENARIOS) {
      const validationError = validatePakistanSite(draftInputs[scenario.id]);
      if (validationError) {
        setToast(`${scenario.name}: ${validationError}`);
        return false;
      }
    }
    const committedInputs = cloneInputs(draftInputs);
    SCENARIOS.forEach((scenario) => {
      const draft = committedInputs[scenario.id];
      committedInputs[scenario.id] = {
        ...draft,
        locationName: String(draft.locationName || "").trim() || `Pakistan site ${Number(draft.latitude).toFixed(4)}, ${Number(draft.longitude).toFixed(4)}`,
        latitude: Number(draft.latitude),
        longitude: Number(draft.longitude),
        capex: Math.max(1, Number(draft.capex)),
        electricityPrice: Math.max(0.01, Number(draft.electricityPrice)),
      };
    });
    setAnalysisRunState("running");
    const succeeded = await runComparison(committedInputs, true);
    if (succeeded) {
      setInputs(committedInputs);
      setAnalysisRunState("success");
      setStatusText("Results current");
      setToast("Solar, Wind, and Wave analyses completed side by side.");
      return true;
    }
    setAnalysisRunState("error");
    return false;
  }

  async function runOneWayExperiment({ parameter, metric, minimum, maximum, points }) {
    if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || minimum >= maximum) {
      setToast("Sensitivity range must contain a finite minimum below the maximum.");
      return;
    }
    setExperimentRunState("running");
    try {
      const paired = await Promise.all(SCENARIOS.map(async (scenario) => [
        scenario.id,
        await apiJson("/api/v1/sensitivity/one-way", {
          analysis: buildAnalysisRequest(scenario, inputs[scenario.id]),
          parameter,
          metric,
          values: linearValues(minimum, maximum, points),
          generation_basis: "p50",
        }),
      ]));
      setOneWayResults(Object.fromEntries(paired));
      setExperimentRunState("success");
      setToast("Shared sensitivity experiment completed for all three models.");
    } catch (error) {
      setExperimentRunState("error");
      setToast(`Sensitivity failed: ${error.message}`);
    }
  }

  async function runWaveCompetitiveness(benchmarkId) {
    const wave = SCENARIOS.find((item) => item.request.technology === "wave");
    const benchmark = rows.find((row) => row.scenario_id === benchmarkId);
    if (!benchmark?.lcoe_usd_per_mwh) {
      setToast("Run the comparison first so a P50 benchmark is available.");
      return;
    }
    const analysis = buildAnalysisRequest(wave, inputs[wave.id]);
    setExperimentRunState("running");
    try {
      const [surface, threshold] = await Promise.all([
        apiJson("/api/v1/sensitivity/two-way", {
          analysis,
          x_parameter: "capex_per_kw",
          x_values: [250, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000],
          y_parameter: "wave_conversion_efficiency",
          y_values: linearValues(0.15, 0.55, 9),
          metric: "lcoe",
          generation_basis: "p50",
          benchmark_value: benchmark.lcoe_usd_per_mwh,
        }),
        apiJson("/api/v1/sensitivity/break-even", {
          analysis,
          parameter: "capex_per_kw",
          metric: "lcoe",
          target_metric_value: benchmark.lcoe_usd_per_mwh,
          lower_bound: 1,
          upper_bound: 8000,
          generation_basis: "p50",
        }),
      ]);
      setWaveResult({
        ...surface,
        baseline_x_value: analysis.financial.capex_per_kw,
        baseline_y_value: analysis.wave.conversion_efficiency,
        baseline_metric_value: rows.find((row) => row.scenario_id === wave.id)?.lcoe_usd_per_mwh ?? null,
      });
      setBreakEvenResult(threshold);
      setExperimentRunState("success");
      setToast("Wave competitiveness screening result is ready.");
    } catch (error) {
      setExperimentRunState("error");
      setToast(`Wave competitiveness failed: ${error.message}`);
    }
  }

  async function runRiskExperiment({ sampleCount, seed }) {
    setRiskRunState("running");
    try {
      const boundedSampleCount = Math.max(1, Math.min(20000, Math.round(sampleCount)));
      const roundedSeed = Math.round(seed);
      const analysisRequests = SCENARIOS.map((scenario) => (
        buildAnalysisRequest(scenario, inputs[scenario.id])
      ));
      const commonPrice = analysisRequests.reduce(
        (total, analysis) => total + analysis.financial.electricity_price_per_mwh,
        0,
      ) / analysisRequests.length;
      const commonDiscountRate = analysisRequests.reduce(
        (total, analysis) => total + analysis.financial.discount_rate,
        0,
      ) / analysisRequests.length;
      const [paired, joint] = await Promise.all([
        Promise.all(SCENARIOS.map(async (scenario) => {
        const scenarioInput = inputs[scenario.id];
        const capex = Number(scenarioInput.capex);
        const price = Number(scenarioInput.electricityPrice);
        const result = await apiJson("/api/v1/risk", {
          analysis: buildAnalysisRequest(scenario, scenarioInput),
          variables: [
            { name: "capex_per_kw", distribution: "triangular", units: "USD/kW", minimum_value: capex * 0.8, mode_value: capex, maximum_value: capex * 1.25 },
            { name: "electricity_price_per_mwh", distribution: "triangular", units: "USD/MWh", minimum_value: price * 0.8, mode_value: price, maximum_value: price * 1.2 },
          ],
          generation_basis: "p50",
          sample_count: boundedSampleCount,
          random_seed: roundedSeed,
          resource_resampling_mode: "annual_empirical",
          irr_hurdle_rate: 0.12,
          lcoe_benchmark_usd_per_mwh: 60,
        });
        return [scenario.id, result];
        })),
        apiJson("/api/v1/risk/joint", {
          technologies: SCENARIOS.map((scenario, index) => {
            const analysis = analysisRequests[index];
            const capex = analysis.financial.capex_per_kw;
            const fixedOpex = analysis.financial.fixed_opex_per_kw_year;
            const variables = [{ name: "capex_per_kw", distribution: "triangular", units: "USD/kW", minimum_value: capex * 0.8, mode_value: capex, maximum_value: capex * 1.25 }];
            if (fixedOpex > 0) {
              variables.push({ name: "fixed_opex_per_kw_year", distribution: "triangular", units: "USD/kW/year", minimum_value: fixedOpex * 0.8, mode_value: fixedOpex, maximum_value: fixedOpex * 1.2 });
            }
            return { analysis, variables };
          }),
          shared_variables: [
            { name: "electricity_price_per_mwh", distribution: "triangular", units: "USD/MWh", minimum_value: commonPrice * 0.8, mode_value: commonPrice, maximum_value: commonPrice * 1.2 },
            { name: "discount_rate", distribution: "triangular", units: "fraction", minimum_value: Math.max(0, commonDiscountRate - 0.02), mode_value: commonDiscountRate, maximum_value: Math.min(0.99, commonDiscountRate + 0.02) },
          ],
          metrics: ["npv", "lcoe"],
          generation_basis: "p50",
          sample_count: boundedSampleCount,
          random_seed: roundedSeed,
          resource_resampling_mode: "annual_empirical",
        }),
      ]);
      setRiskResults(Object.fromEntries(paired));
      setJointRiskResult(joint);
      setRiskRunState("success");
      setToast(`${boundedSampleCount} shared economic worlds completed for Solar, Wind, and Wave.`);
    } catch (error) {
      setRiskRunState("error");
      setToast(`Risk analysis failed: ${error.message}`);
    }
  }

  function exportEvidence() {
    const pack = {
      generated_at: new Date().toISOString(),
      model_status: statusText,
      resource_period: market.resource_period,
      cost_basis: market.cost_basis_label,
      currency_display: currency,
      fx: market.fx,
      scenarios: rows,
      scenario_inputs: SCENARIOS.map((scenario) => buildAnalysisRequest(scenario, inputs[scenario.id])),
      detailed_analyses: analysesById,
      one_way_sensitivity: oneWayResults,
      wave_competitiveness: waveResult,
      break_even: breakEvenResult,
      advanced_risk: riskResults,
      joint_uncertainty: jointRiskResult,
      warnings,
      evidence: SCENARIOS.map(({ id, name, evidence, source }) => ({ id, name, evidence, source })),
      cautions: cautionItems,
    };
    const blob = new Blob([JSON.stringify(pack, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `pak-energy-evidence-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setToast("Evidence pack exported.");
  }

  const currentPage = pageMeta[activeNav] || pageMeta.compare;
  const allDetailedCurrent = SCENARIOS.every((scenario) => analysesById[scenario.id]);

  if (activeNav === "overview") {
    return (
      <>
        <HomePage
          onStart={() => handleNav("build")}
          onMethodology={() => handleNav("methodology")}
          onCompare={() => handleNav("compare")}
        />
        {toast && <div className="toast" role="status">{toast}</div>}
      </>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" type="button" aria-label="Pakistan Energy home" onClick={() => handleNav("overview")}>PAK ENERGY</button>
        <nav aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavButton key={item.id} item={item} active={activeNav === item.id} onClick={() => handleNav(item.id)} />
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <button className="nav-button utility-nav" type="button" onClick={() => openDrawer("settings")}>
          <Gear size={20} /><span>Settings</span>
        </button>
        <button className="nav-button utility-nav" type="button" onClick={() => openDrawer("help")}>
          <Question size={20} /><span>Help</span>
        </button>
        <button className="collapse-button" type="button" aria-label="Collapse navigation" onClick={() => setToast("Navigation stays visible in this desktop view.")}>
          <CaretLeft size={18} />
        </button>
      </aside>

      <main className="main-area" id="comparison-top">
        <header className="topbar">
          <div className="page-title">
            <h1>{currentPage.title}</h1>
            <p>{currentPage.subtitle}</p>
          </div>
          <div className="topbar-actions">
            {activeNav === "compare" ? <>
              <span className={`model-status ${runState}`}>
                {runState === "running" ? <ArrowsClockwise className="spin" size={15} /> : <CheckCircle size={15} weight="fill" />}
                {statusText}
              </span>
              <span className="project-count">Models <strong>3/3</strong></span>
              <button className="secondary-button" type="button" onClick={() => openDrawer("scenarios")}>Manage scenarios</button>
              <button className="primary-button" type="button" onClick={() => runComparison()} disabled={runState === "running"}>
                <Play size={15} weight="fill" /> {runState === "running" ? "Running…" : "Run comparison"}
              </button>
            </> : <>
              <span className={`model-status ${analysisRunState}`}><CheckCircle size={15} weight="fill" />{allDetailedCurrent ? "All three analyses current" : "Ready for a three-model run"}</span>
              {!["methodology", "sources"].includes(activeNav) && <button className="secondary-button" type="button" onClick={() => handleNav("build")}>Edit project inputs</button>}
              <span className="project-count">Models <strong>3/3</strong></span>
            </>}
            <span className="as-of-date"><CalendarBlank size={17} />{PROJECT_DATE}</span>
          </div>
        </header>

        {activeNav === "build" && <BuildPage
          drafts={draftInputs}
          analyses={analysesById}
          runState={analysisRunState}
          onUpdate={updateDraft}
          onRun={runAllDraftAnalyses}
          onOpenResource={() => handleNav("resource")}
          onOpenEconomics={() => handleNav("economics")}
        />}

        {activeNav === "resource" && <ResourcePage analyses={analysesById} onOpenBuild={() => handleNav("build")} />}
        {activeNav === "economics" && <EconomicsPage analyses={analysesById} currency={currency} fxRate={fxRate} money={money} onOpenBuild={() => handleNav("build")} />}
        {activeNav === "sensitivity" && <SensitivityPage results={oneWayResults} waveResult={waveResult} breakEven={breakEvenResult} rows={rows} runState={experimentRunState} onRunOneWay={runOneWayExperiment} onRunWave={runWaveCompetitiveness} />}
        {activeNav === "risk" && <RiskPage results={riskResults} jointResult={jointRiskResult} runState={riskRunState} onRun={runRiskExperiment} />}
        {activeNav === "methodology" && <MethodologyPage version="1.1.0" />}
        {activeNav === "sources" && <SourcesPage assumptions={assumptionCatalog} market={market} onExport={exportEvidence} />}

        {activeNav === "compare" && <>
        <div className="content-frame">
          <div className="workspace">
            <section className="scenario-strip" aria-label="Compared scenarios">
              {SCENARIOS.map((scenario, index) => (
                <ScenarioSummary
                  key={scenario.id}
                  scenario={scenario}
                  scenarioInputs={inputs[scenario.id]}
                  index={index}
                  row={rows.find((row) => row.scenario_id === scenario.id)}
                  selected={selectedId === scenario.id}
                  onSelect={() => setSelectedId(scenario.id)}
                  money={money}
                />
              ))}
            </section>

            <div className="analysis-grid">
              <section className="chart-panel" aria-labelledby="comparison-chart-title">
                <div className="section-heading">
                  <div>
                    <h2 id="comparison-chart-title">Generation uncertainty and LCOE</h2>
                    <p>Generation shows P90–P10 range; LCOE is the P50 financial case.</p>
                  </div>
                  <Info size={15} weight="bold" />
                </div>
                <div className="series-legend" aria-label="Chart legend">
                  {SCENARIOS.map((scenario) => <span key={scenario.id}><i style={{ background: scenario.color }} />{scenario.name}</span>)}
                </div>
                <ReactECharts option={comparisonOption} className="comparison-chart" notMerge lazyUpdate />
                <p className="chart-note"><Info size={14} /> Metrics remain separate. Uncertainty is not collapsed into a single score.</p>
              </section>
              <DecisionLens rows={rows} money={money} />
            </div>

            <div className="lower-grid">
              <section className="sensitivity-panel" id="sensitivity" aria-labelledby="sensitivity-title">
                <div className="section-heading">
                  <div>
                    <h2 id="sensitivity-title">Sensitivity (Wind) <span>— LCOE ({currency}/MWh)</span></h2>
                    <p>CAPEX versus project electricity price (P50)</p>
                  </div>
                  <Info size={15} weight="bold" />
                </div>
                {sensitivityPoints.length ? (
                  <ReactECharts option={sensitivityOption} className="sensitivity-chart" notMerge lazyUpdate />
                ) : (
                  <div className="chart-empty"><ArrowsClockwise className={runState === "running" ? "spin" : ""} size={20} /> Preparing sensitivity grid from the Python model…</div>
                )}
                <p className="assumption-note">Uses P50 generation {formatNumber(rows[0]?.p50_generation_mwh)} MWh/year. CAPEX remains in USD/kW; display currency affects monetary outputs only.</p>
              </section>
              <section className="actions-panel" aria-labelledby="actions-title">
                <h2 id="actions-title">Primary actions</h2>
                <ActionRow icon={ArrowSquareOut} title="Open selected project" description={selectedScenario?.name} onClick={() => openDrawer("scenarios")} />
                <ActionRow icon={FileText} title="View full assumptions" description="Inputs, parameters, and methods" onClick={() => openDrawer("evidence")} />
                <ActionRow icon={DownloadSimple} title="Export evidence pack" description="Data, methods, and audit trail" onClick={exportEvidence} />
              </section>
            </div>
          </div>

          <EvidenceRail onOpenEvidence={() => openDrawer("evidence")} onExport={exportEvidence} />
        </div>

        <footer className="market-footer">
          <div className="currency-control">
            <label htmlFor="currency">Currency</label>
            <select id="currency" value={currency} onChange={(event) => setCurrency(event.target.value)}>
              <option value="USD">USD</option>
              <option value="PKR">PKR</option>
            </select>
            <span>Default costs: IRENA 2025 global benchmarks</span>
          </div>
          <div className="basis-line">
            <span>Resource period 2015–2024</span><i>·</i><span>Cost basis 2025 USD</span><i>·</i>
            <span>{currency === "USD" ? "FX not applied" : `USD/PKR ${formatNumber(fxRate, 4)} · ${formatDateTime(market.fx?.as_of)}`}</span>
          </div>
        </footer>
        </>}
      </main>

      <Drawer
        mode={drawerMode}
        onClose={() => setDrawerMode(null)}
        title={drawerMode === "scenarios" ? "Manage scenarios" : drawerMode === "settings" ? "Currency & cost context" : drawerMode === "help" ? "Using the comparison" : "Evidence log"}
      >
        {drawerMode === "scenarios" && (
          <div className="scenario-form">
            <p className="drawer-intro">Enter any Pakistan site for each technology. The resource provider is queried at the coordinates you enter, then the Python model recalculates generation and economics.</p>
            <p className="location-guidance"><MapPin size={16} weight="fill" />Coordinates are not limited to cities. For wave, use a marine or offshore point.</p>
            {scenarioFormError && <p className="form-error" role="alert"><Warning size={16} weight="bold" />{scenarioFormError}</p>}
            {SCENARIOS.map((scenario) => (
              <fieldset key={scenario.id}>
                <legend><i style={{ background: scenario.color }} />{scenario.name}</legend>
                <label>
                  Site name <span>optional description</span>
                  <input type="text" maxLength="120" value={draftInputs[scenario.id]?.locationName ?? ""} onChange={(event) => updateDraft(scenario.id, "locationName", event.target.value)} />
                </label>
                <div className="coordinate-grid">
                  <label>
                    Latitude <span>23.5–37.1°</span>
                    <input type="number" min={PAKISTAN_COORDINATE_BOUNDS.minimumLatitude} max={PAKISTAN_COORDINATE_BOUNDS.maximumLatitude} step="0.0001" inputMode="decimal" value={draftInputs[scenario.id]?.latitude ?? ""} onChange={(event) => updateDraft(scenario.id, "latitude", event.target.value)} />
                  </label>
                  <label>
                    Longitude <span>60.8–77.9°</span>
                    <input type="number" min={PAKISTAN_COORDINATE_BOUNDS.minimumLongitude} max={PAKISTAN_COORDINATE_BOUNDS.maximumLongitude} step="0.0001" inputMode="decimal" value={draftInputs[scenario.id]?.longitude ?? ""} onChange={(event) => updateDraft(scenario.id, "longitude", event.target.value)} />
                  </label>
                </div>
                <label>
                  CAPEX <span>USD/kW</span>
                  <input type="number" min="1" step="1" value={draftInputs[scenario.id]?.capex ?? ""} onChange={(event) => updateDraft(scenario.id, "capex", event.target.value)} />
                </label>
                <label>
                  Electricity sale price <span>USD/MWh</span>
                  <input type="number" min="1" step="1" value={draftInputs[scenario.id]?.electricityPrice ?? ""} onChange={(event) => updateDraft(scenario.id, "electricityPrice", event.target.value)} />
                </label>
                <small>{scenario.id === "karachi-wave" ? "Marine/offshore coordinate expected. Research scenario inputs; no mature generic wave benchmark." : `Any Pakistan coordinate is accepted. IRENA 2025 global CAPEX default: USD ${scenario.defaultCapex}/kW.`}</small>
              </fieldset>
            ))}
            <div className="drawer-actions">
              <button className="secondary-button" type="button" onClick={() => setDraftInputs(scenarioInputsFromDefaults())}>Reset defaults</button>
              <button className="primary-button" type="button" onClick={applyScenarioChanges}><Play size={14} weight="fill" />Apply & run</button>
            </div>
          </div>
        )}

        {drawerMode === "settings" && (
          <div className="settings-content">
            <div className="setting-block">
              <CurrencyDollar size={22} />
              <div><h3>Display currency</h3><p>Financial calculations remain in USD. PKR is a transparent display conversion.</p></div>
            </div>
            <label className="select-label" htmlFor="drawer-currency">Currency
              <select id="drawer-currency" value={currency} onChange={(event) => setCurrency(event.target.value)}><option value="USD">USD</option><option value="PKR">PKR</option></select>
            </label>
            <dl className="market-context-list">
              <div><dt>Cost basis</dt><dd>{market.cost_basis_label}</dd></div>
              <div><dt>USD/PKR</dt><dd>{formatNumber(fxRate, 4)}</dd></div>
              <div><dt>Rate date</dt><dd>{formatDateTime(market.fx?.as_of)}</dd></div>
              <div><dt>Rate source</dt><dd>{market.fx?.source_name}</dd></div>
              <div><dt>Status</dt><dd>{market.fx?.is_live ? "Live provider response" : "Dated fallback"}{market.fx?.is_stale ? " · stale" : ""}</dd></div>
            </dl>
            <p className="disclosure"><Warning size={16} />{market.fx?.warning}</p>
            <div className="source-links">
              <a href={market.fx?.source_url} target="_blank" rel="noreferrer">Rate source <ArrowSquareOut size={14} /></a>
              <a href={market.fx?.official_reference_url} target="_blank" rel="noreferrer">SBP official reference <ArrowSquareOut size={14} /></a>
            </div>
          </div>
        )}

        {drawerMode === "evidence" && (
          <div className="evidence-drawer">
            <p className="drawer-intro">Evidence strength describes the resource and model evidence—not the attractiveness of the investment.</p>
            {SCENARIOS.map((scenario) => (
              <article key={scenario.id}>
                <header><div><i style={{ background: scenario.color }} /><strong>{scenario.name}</strong></div><b>{scenario.evidence}</b></header>
                <dl><div><dt>Resource</dt><dd>{scenario.source}</dd></div><div><dt>Period</dt><dd>2015–2024</dd></div><div><dt>Cost basis</dt><dd>{scenario.id === "karachi-wave" ? "Explicit research scenario" : "IRENA 2025 global benchmark"}</dd></div></dl>
              </article>
            ))}
            <h3>Model warnings</h3>
            <ul className="warning-list">
              {(warnings.length ? warnings : cautionItems.map((item) => item.body)).map((warning) => <li key={warning}><Warning size={15} />{warning}</li>)}
            </ul>
            <p className="disclosure"><Database size={16} />Resource files, assumptions, and generated evidence stay in the D-drive project.</p>
          </div>
        )}

        {drawerMode === "help" && (
          <div className="help-content">
            <h3>Start with the decision metric</h3>
            <p>Use LCOE for generation cost, IRR for the project return under the entered tariff, and the P90–P10 range for resource uncertainty.</p>
            <h3>Do not read the cards as a single ranking</h3>
            <p>The simulator deliberately avoids one composite score because financing, cost, and resource uncertainty answer different questions.</p>
            <h3>Check the evidence rail</h3>
            <p>Wave remains a research scenario. Its current output is useful for sensitivity exploration, not a bankable market forecast.</p>
          </div>
        )}
      </Drawer>

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
