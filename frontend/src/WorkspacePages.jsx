import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import {
  ArrowRight,
  BookOpenText,
  ChartLineUp,
  CheckCircle,
  CurrencyDollar,
  Database,
  DownloadSimple,
  Flask,
  Function as FunctionIcon,
  Gauge,
  MapPin,
  Play,
  ShieldCheck,
  SlidersHorizontal,
  Sun,
  Warning,
  Waves,
  Wind as WindIcon,
} from "@phosphor-icons/react";

import {
  annualGenerationOption,
  economicsOverviewOption,
  oneWaySensitivityOption,
  riskHistogramOption,
  waveCompetitivenessOption,
} from "./charts.js";
import { PAKISTAN_COORDINATE_BOUNDS, SCENARIOS } from "./config.js";

const technologyIcons = {
  solar: Sun,
  wind: WindIcon,
  wave: Waves,
};

const metricLabels = {
  lcoe: "LCOE",
  npv: "NPV",
  irr: "Project IRR",
  first_year_generation: "First-year generation",
  lifetime_generation: "Lifetime generation",
  capacity_factor: "Capacity factor",
  simple_payback: "Simple payback",
  discounted_payback: "Discounted payback",
};

const parameterLabels = {
  capex_per_kw: "CAPEX (USD/kW)",
  fixed_opex_per_kw_year: "Fixed OPEX (USD/kW/year)",
  electricity_price_per_mwh: "Electricity price (USD/MWh)",
  discount_rate: "Discount rate",
  solar_system_losses: "Solar system losses",
  solar_tilt_deg: "Solar tilt (degrees)",
  wind_hub_height_m: "Wind hub height (m)",
  wind_availability: "Wind availability",
  wave_conversion_efficiency: "Wave conversion efficiency",
  wave_capture_width_m: "Wave capture width (m)",
};

function number(value, digits = 0) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function percent(value, digits = 1) {
  return value == null || !Number.isFinite(Number(value)) ? "—" : `${number(Number(value) * 100, digits)}%`;
}

function Tabs({ items, value, onChange, label }) {
  return (
    <div className="page-tabs" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={value === item.id}
          className={value === item.id ? "is-active" : ""}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function EmptyAnalysis({ onOpenBuild, noun = "this page" }) {
  return (
    <section className="empty-analysis">
      <Flask size={27} weight="duotone" aria-hidden="true" />
      <div>
        <h2>Run a project analysis first</h2>
        <p>{noun} uses the full annual resource record and Python financial model, not placeholder values.</p>
      </div>
      <button className="primary-button" type="button" onClick={onOpenBuild}>Open New Analysis <ArrowRight size={15} /></button>
    </section>
  );
}

export function HomePage({ onStart, onMethodology, onCompare }) {
  const questions = [
    "What can this coordinate generate?",
    "What will the project cost over its life?",
    "How uncertain is the result?",
    "When could wave become competitive?",
  ];
  return (
    <main className="home-page">
      <header className="home-nav">
        <button className="home-brand" type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
          <span>PE</span><strong>PAKISTAN<br />ENERGY LAB</strong>
        </button>
        <nav aria-label="Home navigation">
          <button type="button" onClick={onMethodology}>How it works</button>
          <button type="button" onClick={onCompare}>Compare models</button>
          <button className="home-nav-cta" type="button" onClick={onStart}>Start simulation</button>
        </nav>
      </header>

      <section className="home-hero">
        <div className="home-hero-copy">
          <p className="eyebrow"><i /> RENEWABLE-ENERGY ENGINEERING FOR PAKISTAN</p>
          <h1>From a Pakistan coordinate to an <span>engineering decision.</span></h1>
          <p className="home-lede">Compare solar, wind and wave through one traceable chain: historical resource, technology physics, P90/P50/P10 generation and project economics.</p>
          <div className="hero-actions">
            <button className="home-primary" type="button" onClick={onStart}>Start a new analysis <ArrowRight size={18} weight="bold" /></button>
            <button className="home-secondary" type="button" onClick={onMethodology}><BookOpenText size={18} /> Explore methodology</button>
          </div>
          <p className="home-trust"><ShieldCheck size={18} weight="duotone" /> Python is the scientific source of truth. Assumptions and warnings stay visible.</p>
        </div>

        <aside className="decision-brief" aria-label="Questions the simulator answers">
          <p>YOUR ENGINEERING BRIEF</p>
          <ol>
            {questions.map((question) => <li key={question}><CheckCircle size={17} weight="fill" />{question}</li>)}
          </ol>
          <small>And most importantly</small>
          <strong>Under what conditions?</strong>
        </aside>
      </section>

      <section className="home-technology-section">
        <div className="home-section-heading">
          <p>01 / THREE PHYSICAL MODELS</p>
          <div><h2>One site. Three different energy systems.</h2><p>The comparison never hides unlike assumptions behind a single score.</p></div>
        </div>
        <div className="technology-editorial-grid">
          {SCENARIOS.map((scenario, index) => {
            const Icon = technologyIcons[scenario.request.technology];
            return (
              <article key={scenario.id}>
                <header><span>0{index + 1}</span><Icon size={25} weight="duotone" /></header>
                <h3>{scenario.name}</h3>
                <p>{scenario.request.technology === "solar" ? "Irradiance, temperature response, system losses and degradation." : scenario.request.technology === "wind" ? "Hub-height wind, air density and a transparent turbine power curve." : "Wave-height and period physics with an explicit pre-commercial device case."}</p>
                <small>{scenario.evidence} resource evidence</small>
              </article>
            );
          })}
        </div>
      </section>

      <section className="home-pipeline">
        <div><p>02 / MODEL CHAIN</p><h2>The calculation has a visible spine.</h2></div>
        <ol>
          {["Coordinates", "Resource data", "Technology physics", "Annual statistics", "Lifecycle", "Economics", "Risk"].map((step, index) => (
            <li key={step}><span>{String(index + 1).padStart(2, "0")}</span>{step}</li>
          ))}
        </ol>
      </section>
    </main>
  );
}

function Field({ label, unit, children }) {
  return <label className="workspace-field"><span>{label}</span><small>{unit}</small>{children}</label>;
}

export function BuildPage({ drafts, analyses, runState, onUpdate, onRun, onOpenResource, onOpenEconomics }) {
  return (
    <div className="page-workspace build-page">
      <section className="parallel-page-intro">
        <div><p className="eyebrow">THREE MODELS / ONE CONTROLLED RUN</p><h2>Set every case side by side.</h2><p>Each technology keeps its own coordinate, physics and financial assumptions. Running the workspace recalculates all three together.</p></div>
        <button className="primary-button parallel-run-button" type="button" disabled={runState === "running"} onClick={onRun}><Play size={16} weight="fill" />{runState === "running" ? "Running all three…" : "Run Solar + Wind + Wave"}</button>
      </section>

      <section className="parallel-model-grid input-model-grid" aria-label="Solar, wind and wave model inputs">
        {SCENARIOS.map((scenario, index) => {
          const draft = drafts[scenario.id];
          const analysis = analyses[scenario.id];
          const p50 = analysis?.evaluations?.p50;
          const Icon = technologyIcons[scenario.request.technology];
          return <article className="parallel-model-card" key={scenario.id} style={{ "--model-color": scenario.color }}>
            <header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>{scenario.technologyLabel}</p></div><Icon size={24} weight="duotone" /></header>
            <div className="parallel-card-section"><h3><MapPin size={15} /> Site</h3><Field label="Site name" unit="editable"><input type="text" maxLength="120" value={draft.locationName} onChange={(event) => onUpdate(scenario.id, "locationName", event.target.value)} /></Field><div className="form-grid two-columns"><Field label="Latitude" unit="°N"><input type="number" step="0.0001" min={PAKISTAN_COORDINATE_BOUNDS.minimumLatitude} max={PAKISTAN_COORDINATE_BOUNDS.maximumLatitude} value={draft.latitude} onChange={(event) => onUpdate(scenario.id, "latitude", event.target.value)} /></Field><Field label="Longitude" unit="°E"><input type="number" step="0.0001" min={PAKISTAN_COORDINATE_BOUNDS.minimumLongitude} max={PAKISTAN_COORDINATE_BOUNDS.maximumLongitude} value={draft.longitude} onChange={(event) => onUpdate(scenario.id, "longitude", event.target.value)} /></Field></div>{scenario.request.technology === "wave" && <p className="inline-caution"><Warning size={14} />Use an offshore coordinate.</p>}</div>
            <div className="parallel-card-section"><h3><Icon size={15} /> Project & physics</h3><div className="form-grid two-columns"><Field label="Capacity" unit="MW"><input type="number" min="0.1" value={draft.capacity} onChange={(event) => onUpdate(scenario.id, "capacity", event.target.value)} /></Field><Field label="Lifetime" unit="years"><input type="number" min="1" max="100" value={draft.lifetime} onChange={(event) => onUpdate(scenario.id, "lifetime", event.target.value)} /></Field>{scenario.request.technology === "solar" && <><Field label="Array tilt" unit="degrees"><input type="number" min="0" max="90" value={draft.solarTilt} onChange={(event) => onUpdate(scenario.id, "solarTilt", event.target.value)} /></Field><Field label="System losses" unit="%"><input type="number" min="0" max="99" value={draft.solarLossPct} onChange={(event) => onUpdate(scenario.id, "solarLossPct", event.target.value)} /></Field></>}{scenario.request.technology === "wind" && <><Field label="Hub height" unit="m"><input type="number" min="1" value={draft.windHubHeight} onChange={(event) => onUpdate(scenario.id, "windHubHeight", event.target.value)} /></Field><Field label="Availability" unit="%"><input type="number" min="1" max="100" value={draft.windAvailabilityPct} onChange={(event) => onUpdate(scenario.id, "windAvailabilityPct", event.target.value)} /></Field></>}{scenario.request.technology === "wave" && <><Field label="Efficiency" unit="%"><input type="number" min="1" max="100" value={draft.waveEfficiencyPct} onChange={(event) => onUpdate(scenario.id, "waveEfficiencyPct", event.target.value)} /></Field><Field label="Capture width" unit="m"><input type="number" min="0.1" value={draft.waveCaptureWidth} onChange={(event) => onUpdate(scenario.id, "waveCaptureWidth", event.target.value)} /></Field></>}</div></div>
            <div className="parallel-card-section"><h3><CurrencyDollar size={15} /> Economics</h3><div className="form-grid two-columns"><Field label="CAPEX" unit="USD/kW"><input type="number" min="1" value={draft.capex} onChange={(event) => onUpdate(scenario.id, "capex", event.target.value)} /></Field><Field label="Fixed OPEX" unit="USD/kW/y"><input type="number" min="0" value={draft.fixedOpex} onChange={(event) => onUpdate(scenario.id, "fixedOpex", event.target.value)} /></Field><Field label="Sale price" unit="USD/MWh"><input type="number" min="0.01" value={draft.electricityPrice} onChange={(event) => onUpdate(scenario.id, "electricityPrice", event.target.value)} /></Field><Field label="Discount rate" unit="%"><input type="number" min="0" max="99" value={draft.discountRatePct} onChange={(event) => onUpdate(scenario.id, "discountRatePct", event.target.value)} /></Field></div></div>
            <details className="advanced-inputs"><summary>Advanced assumptions</summary><div className="form-grid two-columns"><Field label="Degradation" unit="%/year"><input type="number" min="0" max="99" value={draft.degradationPct} onChange={(event) => onUpdate(scenario.id, "degradationPct", event.target.value)} /></Field><Field label="Variable OPEX" unit="USD/MWh"><input type="number" min="0" value={draft.variableOpex} onChange={(event) => onUpdate(scenario.id, "variableOpex", event.target.value)} /></Field><Field label="Start date" unit="historical"><input type="date" value={draft.startDate} onChange={(event) => onUpdate(scenario.id, "startDate", event.target.value)} /></Field><Field label="End date" unit="historical"><input type="date" value={draft.endDate} onChange={(event) => onUpdate(scenario.id, "endDate", event.target.value)} /></Field><Field label="Provider" unit="fallback-aware"><select value={draft.provider} onChange={(event) => onUpdate(scenario.id, "provider", event.target.value)}><option value="auto">Auto</option><option value="open_meteo">Open-Meteo</option><option value="copernicus">Copernicus</option></select></Field>{scenario.request.technology === "wind" && <Field label="Turbine curve" unit="generation model"><select value={draft.windPowerCurve} onChange={(event) => onUpdate(scenario.id, "windPowerCurve", event.target.value)}><option value="iea_reference_3_4mw_130">IEA Reference 3.4 MW (tabulated)</option><option value="cubic_fallback">Cubic fallback</option></select></Field>}</div></details>
            {p50 ? <div className="parallel-result"><p><CheckCircle size={14} weight="fill" /> Current result</p><strong>{number(analysis.generation_statistics.p50_mwh)} MWh</strong><small>P50 annual generation</small><dl><div><dt>LCOE</dt><dd>USD {number(p50.lcoe_usd_per_mwh, 2)}/MWh</dd></div><div><dt>Project IRR</dt><dd>{percent(p50.project_irr, 2)}</dd></div></dl></div> : <p className="parallel-pending">Run all three models to populate this case.</p>}
          </article>;
        })}
      </section>
      <div className="parallel-page-actions"><p>Coordinates are independent. Solar and wind may share a site while wave uses an offshore point.</p><button type="button" onClick={onOpenResource}>Open three-way resource evidence <ArrowRight size={15} /></button><button type="button" onClick={onOpenEconomics}>Open three-way economics <ArrowRight size={15} /></button></div>
    </div>
  );
}

export function ResourcePage({ analyses, onOpenBuild }) {
  const [tab, setTab] = useState("record");
  if (!SCENARIOS.every((scenario) => analyses[scenario.id])) return <div className="page-workspace"><EmptyAnalysis onOpenBuild={onOpenBuild} noun="The three-way resource workspace" /></div>;
  return (
    <div className="page-workspace">
      <Tabs label="Resource views" value={tab} onChange={setTab} items={[{ id: "record", label: "Resource record" }, { id: "annual", label: "Annual generation" }, { id: "quality", label: "Quality & warnings" }]} />
      {tab === "record" && <section className="parallel-model-grid">{SCENARIOS.map((scenario, index) => { const analysis = analyses[scenario.id]; const stats = analysis.generation_statistics; const Icon = technologyIcons[scenario.request.technology]; return <article className="parallel-model-card resource-card" key={scenario.id} style={{ "--model-color": scenario.color }}><header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>{scenario.technologyLabel}</p></div><Icon size={23} weight="duotone" /></header><div className="resource-metric-stack"><div><span>P90</span><strong>{number(stats.p90_mwh)} MWh</strong></div><div className="is-primary"><span>P50</span><strong>{number(stats.p50_mwh)} MWh</strong></div><div><span>P10</span><strong>{number(stats.p10_mwh)} MWh</strong></div></div><dl className="evidence-table"><div><dt>Requested</dt><dd>{number(analysis.resource.requested_latitude, 4)}, {number(analysis.resource.requested_longitude, 4)}</dd></div><div><dt>Resolved grid</dt><dd>{number(analysis.resource.resolved_latitude, 4)}, {number(analysis.resource.resolved_longitude, 4)}</dd></div><div><dt>Source</dt><dd>{analysis.resource.source_name}</dd></div><div><dt>Dataset</dt><dd>{analysis.resource.dataset_name}</dd></div><div><dt>Samples</dt><dd>{number(analysis.resource.sample_count)}</dd></div><div><dt>Resource CV</dt><dd>{percent(stats.coefficient_of_variation, 2)}</dd></div></dl></article>; })}</section>}
      {tab === "annual" && <section className="parallel-model-grid chart-model-grid">{SCENARIOS.map((scenario, index) => { const analysis = analyses[scenario.id]; const stats = analysis.generation_statistics; const chart = annualGenerationOption(analysis.annual_generation, stats, scenario.color); return <article className="parallel-model-card chart-page-panel" key={scenario.id} style={{ "--model-color": scenario.color }}><header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>Historical annual generation</p></div><ChartLineUp size={21} /></header><ReactECharts option={chart} className="parallel-chart" notMerge /><div className="record-extremes"><span>Low <strong>{stats.worst_year}</strong> · {number(stats.minimum_mwh)} MWh</span><span>High <strong>{stats.best_year}</strong> · {number(stats.maximum_mwh)} MWh</span></div></article>; })}</section>}
      {tab === "quality" && <section className="parallel-model-grid">{SCENARIOS.map((scenario, index) => { const analysis = analyses[scenario.id]; const stats = analysis.generation_statistics; return <article className="parallel-model-card" key={scenario.id} style={{ "--model-color": scenario.color }}><header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>Completeness & cautions</p></div><Gauge size={21} /></header><dl className="evidence-table"><div><dt>Accepted years</dt><dd>{stats.accepted_years.join(", ")}</dd></div><div><dt>Excluded years</dt><dd>{stats.excluded_years.length ? stats.excluded_years.join(", ") : "None"}</dd></div><div><dt>Annual mean</dt><dd>{number(stats.mean_mwh)} MWh</dd></div><div><dt>Annual median</dt><dd>{number(stats.median_mwh)} MWh</dd></div></dl><ul className="plain-warning-list compact-warnings">{(analysis.warnings.length ? analysis.warnings : ["No additional resource warning returned."]).slice(0, 4).map((warning) => <li key={warning}><Warning size={14} />{warning}</li>)}</ul></article>; })}</section>}
    </div>
  );
}

export function EconomicsPage({ analyses, currency, fxRate, money, onOpenBuild }) {
  const [tab, setTab] = useState("summary");
  if (!SCENARIOS.every((scenario) => analyses[scenario.id])) return <div className="page-workspace"><EmptyAnalysis onOpenBuild={onOpenBuild} noun="The three-way economics workspace" /></div>;
  return (
    <div className="page-workspace">
      <Tabs label="Economics views" value={tab} onChange={setTab} items={[{ id: "summary", label: "Project summary" }, { id: "cases", label: "P90 / P50 / P10" }, { id: "calculation", label: "How calculated" }]} />
      {tab === "summary" && <section className="parallel-model-grid economics-model-grid">{SCENARIOS.map((scenario, index) => { const analysis = analyses[scenario.id]; const p50 = analysis.evaluations.p50; const economicsChart = economicsOverviewOption(p50, currency, fxRate); return <article className="parallel-model-card chart-page-panel" key={scenario.id} style={{ "--model-color": scenario.color }}><header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>P50 unlevered project case</p></div><CurrencyDollar size={22} /></header><div className="economics-key-metrics"><div><span>LCOE</span><strong>{money(p50.lcoe_usd_per_mwh, 2)}/MWh</strong></div><div><span>NPV</span><strong>{money(p50.npv_usd, 0)}</strong></div><div><span>IRR</span><strong>{percent(p50.project_irr, 2)}</strong></div><div><span>Payback</span><strong>{p50.simple_payback_years == null ? "Not reached" : `${number(p50.simple_payback_years, 1)} y`}</strong></div></div><ReactECharts option={economicsChart} className="parallel-economics-chart" notMerge /><dl className="evidence-table"><div><dt>Initial CAPEX</dt><dd>{money(p50.initial_capex_usd, 0)}</dd></div><div><dt>Lifetime revenue</dt><dd>{money(p50.lifetime_revenue_usd, 0)}</dd></div><div><dt>Lifetime generation</dt><dd>{number(p50.lifetime_generation_mwh)} MWh</dd></div></dl></article>; })}</section>}
      {tab === "cases" && <section className="parallel-model-grid case-model-grid">{SCENARIOS.map((scenario, index) => { const analysis = analyses[scenario.id]; return <article className="parallel-model-card" key={scenario.id} style={{ "--model-color": scenario.color }}><header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>Resource cases</p></div><ChartLineUp size={21} /></header><div className="responsive-table compact-table"><table><thead><tr><th>Case</th><th>Generation</th><th>LCOE</th><th>IRR</th></tr></thead><tbody>{["p90", "p50", "p10"].map((basis) => { const item = analysis.evaluations[basis]; return <tr key={basis}><th>{basis.toUpperCase()}</th><td>{number(item.first_year_generation_mwh)} MWh</td><td>{money(item.lcoe_usd_per_mwh, 2)}</td><td>{percent(item.project_irr, 2)}</td></tr>; })}</tbody></table></div></article>; })}</section>}
      {tab === "calculation" && <div className="formula-grid">
        <article><span>01 / INITIAL COST</span><h3>CAPEX</h3><code>CapacityMW × 1,000 × CAPEXUSD/kW</code><p>Installed capacity is converted from MW to kW before applying the entered cost rate.</p></article>
        <article><span>02 / DISCOUNTED VALUE</span><h3>NPV</h3><code>Σ CFt / (1 + r)^t</code><p>Project cash flows are unlevered. Debt and tax are not silently added.</p></article>
        <article><span>03 / GENERATION COST</span><h3>LCOE</h3><code>PV(costs) / PV(energy)</code><p>LCOE does not depend on the electricity selling price.</p></article>
        <article><span>04 / RETURN</span><h3>Project IRR</h3><code>NPV(r) = 0</code><p>Ambiguous or unsupported cash-flow structures return undefined rather than a deceptive rate.</p></article>
      </div>}
    </div>
  );
}

export function SensitivityPage({ results, waveResult, breakEven, rows, runState, onRunOneWay, onRunWave }) {
  const [tab, setTab] = useState("one-way");
  const [parameter, setParameter] = useState("capex_per_kw");
  const [metric, setMetric] = useState("lcoe");
  const [minimum, setMinimum] = useState("600");
  const [maximum, setMaximum] = useState("1400");
  const [points, setPoints] = useState("9");
  const waveChart = useMemo(() => waveCompetitivenessOption(waveResult), [waveResult]);
  const waveSummary = useMemo(() => {
    const validPoints = (waveResult?.points || []).filter((point) => Number.isFinite(Number(point.metric_value)));
    const best = validPoints.reduce((lowest, point) => (
      !lowest || Number(point.metric_value) < Number(lowest.metric_value) ? point : lowest
    ), null);
    const benchmark = Number(waveResult?.benchmark_value);
    const bestLcoe = Number(best?.metric_value);
    const multiple = Number.isFinite(benchmark) && benchmark > 0 && Number.isFinite(bestLcoe) ? bestLcoe / benchmark : null;
    return {
      best,
      benchmark,
      multiple,
      competitiveCount: validPoints.filter((point) => point.is_competitive === true).length,
      totalCount: validPoints.length,
    };
  }, [waveResult]);
  function changeParameter(value) {
    setParameter(value);
    const ranges = { capex_per_kw: [500, 5500], fixed_opex_per_kw_year: [10, 180], electricity_price_per_mwh: [30, 140], discount_rate: [0.05, 0.18] };
    const [low, high] = ranges[value] || [0, 1];
    setMinimum(String(low)); setMaximum(String(high));
  }
  return (
    <div className="page-workspace">
      <Tabs label="Sensitivity views" value={tab} onChange={setTab} items={[{ id: "one-way", label: "One-way sensitivity" }, { id: "wave-frontier", label: "Wave competitiveness" }, { id: "break-even", label: "Break-even detail" }]} />
      {tab === "one-way" && <>
        <section className="risk-toolbar sensitivity-toolbar">
          <Field label="Parameter" unit="shared across all three"><select value={parameter} onChange={(event) => changeParameter(event.target.value)}><option value="capex_per_kw">CAPEX</option><option value="fixed_opex_per_kw_year">Fixed OPEX</option><option value="electricity_price_per_mwh">Electricity price</option><option value="discount_rate">Discount rate</option></select></Field>
          <Field label="Target output" unit="metric"><select value={metric} onChange={(event) => setMetric(event.target.value)}><option value="lcoe">LCOE</option><option value="npv">NPV</option><option value="irr">Project IRR</option><option value="first_year_generation">First-year generation</option><option value="capacity_factor">Capacity factor</option></select></Field>
          <Field label="Minimum" unit="range"><input type="number" step="any" value={minimum} onChange={(event) => setMinimum(event.target.value)} /></Field>
          <Field label="Maximum" unit="range"><input type="number" step="any" value={maximum} onChange={(event) => setMaximum(event.target.value)} /></Field>
          <Field label="Points" unit="2–101"><input type="number" min="2" max="101" value={points} onChange={(event) => setPoints(event.target.value)} /></Field>
          <button className="primary-button" type="button" disabled={runState === "running"} onClick={() => onRunOneWay({ parameter, metric, minimum: Number(minimum), maximum: Number(maximum), points: Number(points) })}><Play size={15} weight="fill" />{runState === "running" ? "Running all three…" : "Run all three"}</button>
        </section>
        <section className="parallel-model-grid chart-model-grid">
          {SCENARIOS.map((scenario, index) => {
            const result = results[scenario.id];
            const chart = oneWaySensitivityOption(result, parameterLabels[parameter], metricLabels[metric]);
            return <article className="parallel-model-card chart-page-panel" key={scenario.id} style={{ "--model-color": scenario.color }}><header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>{result ? `${parameterLabels[result.parameter]} → ${metricLabels[result.metric]}` : "Awaiting shared experiment"}</p></div><SlidersHorizontal size={21} /></header>{result ? <><ReactECharts option={chart} className="parallel-chart" notMerge /><p className="chart-footnote">Baseline {number(result.baseline_parameter_value, 3)} → {number(result.baseline_metric_value, 3)}</p></> : <div className="chart-placeholder"><ChartLineUp size={25} /><p>Run the shared range to compare all three models.</p></div>}</article>;
          })}
        </section>
      </>}
      {tab === "wave-frontier" && <>
        <section className="parallel-model-grid benchmark-model-grid">
          {SCENARIOS.map((scenario, index) => {
            const row = rows.find((item) => item.scenario_id === scenario.id);
            return <article className="benchmark-card" key={scenario.id} style={{ "--model-color": scenario.color }}><span>0{index + 1}</span><h3>{scenario.name}</h3><strong>USD {number(row?.lcoe_usd_per_mwh, 2)}/MWh</strong><p>{scenario.request.technology === "wave" ? "Base case to improve" : "P50 comparison benchmark"}</p></article>;
          })}
        </section>
        {waveResult && waveSummary.best && <section className={`wave-screening-result ${waveSummary.competitiveCount ? "is-competitive" : "is-outside-range"}`} aria-live="polite">
          <div className="wave-result-lead">
            <p className="eyebrow">SCREENING RESULT</p>
            <div className="wave-result-title">
              {waveSummary.competitiveCount ? <CheckCircle size={22} weight="fill" /> : <Warning size={22} weight="fill" />}
              <h2>{waveSummary.competitiveCount ? "A competitive region appears in the tested range" : "No competitive case in the tested range"}</h2>
            </div>
            <p>{waveSummary.competitiveCount
              ? `${waveSummary.competitiveCount} modeled combinations meet or beat the Solar P50 LCOE benchmark.`
              : `The best of ${waveSummary.totalCount} modeled combinations remains ${number(waveSummary.multiple, 1)}× the Solar P50 LCOE. The missing frontier is a result, not a chart error.`}</p>
          </div>
          <dl className="wave-result-metrics">
            <div><dt>Best tested LCOE</dt><dd>USD {number(waveSummary.best.metric_value, 1)}/MWh</dd></div>
            <div><dt>Solar benchmark</dt><dd>USD {number(waveSummary.benchmark, 2)}/MWh</dd></div>
            <div><dt>Best tested inputs</dt><dd>USD {number(waveSummary.best.x_value)}/kW · {percent(waveSummary.best.y_value, 0)}</dd></div>
            <div><dt>Competitive cells</dt><dd>{waveSummary.competitiveCount} / {waveSummary.totalCount}</dd></div>
          </dl>
        </section>}
        <div className="wave-frontier-layout">
          <section className="frontier-intro">
            <p className="eyebrow">FLAGSHIP ACADEMIC VIEW</p>
            <h2>When could wave compete?</h2>
            <p>Test CAPEX and conversion efficiency against the Solar P50 benchmark. Wind, Solar and the current Wave case remain visible as the decision context.</p>
            <button className="primary-button" type="button" disabled={runState === "running"} onClick={() => onRunWave("jhimpir-solar")}><Play size={15} weight="fill" />{runState === "running" ? "Calculating conditions…" : waveResult ? "Recalculate conditions" : "Calculate conditions"}</button>
            <p className="frontier-method-note">81 full model evaluations · fixed Wave OPEX and device assumptions · P50 generation basis</p>
          </section>
          <section className="editorial-panel chart-page-panel wave-chart-panel">
            {waveResult ? <>
              <header className="wave-chart-header"><div><p className="eyebrow">RELATIVE COST SURFACE</p><h3>Wave LCOE as a multiple of Solar</h3><p>Decision bands replace a raw color gradient. Hover any cell for LCOE and exact benchmark multiple.</p></div><div><span>Target</span><strong>USD {number(waveSummary.benchmark, 2)}/MWh</strong></div></header>
              <ReactECharts option={waveChart} className="frontier-chart" notMerge />
              <p className="wave-chart-note">The current Wave case is marked on the grid. A dashed boundary appears only where modeled cells meet the Solar benchmark.</p>
            </> : <div className="chart-placeholder"><Waves size={29} /><p>Run the screening to see the best modeled case, the benchmark gap and the full quantitative surface.</p></div>}
          </section>
        </div>
      </>}
      {tab === "break-even" && <section className={`break-even-panel ${breakEven && !breakEven.converged ? "is-unbracketed" : ""}`}>
        <div>
          <p className="eyebrow">ROOT-FINDING RESULT</p>
          <h2>{breakEven?.converged ? "Wave CAPEX reaches the Solar benchmark" : "CAPEX alone does not close the modeled gap"}</h2>
          <p>{breakEven?.converged
            ? "The threshold is a numerical solution inside the searched interval, with all other Wave assumptions held constant."
            : "Even the low end of the CAPEX search remains above Solar because fixed OPEX, resource yield and device performance still constrain LCOE."}</p>
          {breakEven?.warning && <p className="break-even-warning"><Warning size={15} weight="fill" />{breakEven.warning}</p>}
        </div>
        {breakEven ? <dl>
          <div><dt>Status</dt><dd>{breakEven.converged ? "Threshold found" : "Outside search range"}</dd></div>
          <div><dt>CAPEX threshold</dt><dd>{breakEven.break_even_parameter_value == null ? "No CAPEX-only solution" : `USD ${number(breakEven.break_even_parameter_value, 1)}/kW`}</dd></div>
          <div><dt>Search interval</dt><dd>USD {number(breakEven.lower_bound, 0)}–{number(breakEven.upper_bound, 0)}/kW</dd></div>
          <div><dt>Solar target</dt><dd>USD {number(breakEven.target_metric_value, 2)}/MWh</dd></div>
          <div><dt>Best tested surface</dt><dd>{waveSummary.best ? `USD ${number(waveSummary.best.metric_value, 1)}/MWh` : "—"}</dd></div>
          <div><dt>Iterations</dt><dd>{breakEven.iterations}</dd></div>
        </dl> : <p className="inline-caution"><Warning size={15} />Run the Wave competitiveness view to calculate this threshold.</p>}
      </section>}
    </div>
  );
}

function pairedProbability(result, metric, rowTechnology, columnTechnology) {
  if (!result || rowTechnology === columnTechnology) return null;
  const comparison = result.comparisons?.find((item) => (
    item.metric === metric
    && ((item.technology_a === rowTechnology && item.technology_b === columnTechnology)
      || (item.technology_a === columnTechnology && item.technology_b === rowTechnology))
  ));
  if (!comparison) return null;
  return comparison.technology_a === rowTechnology
    ? comparison.probability_a_better
    : comparison.probability_b_better;
}

function JointProbabilityMatrix({ result, metric }) {
  const direction = metric === "lcoe" ? "lower" : "higher";
  const symbol = metric === "lcoe" ? "<" : ">";
  return <article className="joint-matrix-panel">
    <header><div><p className="eyebrow">PAIRED {metric.toUpperCase()}</p><h2>{metric.toUpperCase()} head-to-head</h2></div><span>{direction} is better</span></header>
    <div className="joint-matrix-table" role="table" aria-label={`Paired ${metric.toUpperCase()} probabilities`}>
      <div className="joint-matrix-row joint-matrix-head" role="row"><span>Probability</span>{SCENARIOS.map((scenario) => <strong key={scenario.request.technology}>{scenario.name}</strong>)}</div>
      {SCENARIOS.map((row) => <div className="joint-matrix-row" role="row" key={row.request.technology}>
        <strong>{row.name}</strong>
        {SCENARIOS.map((column) => {
          const probability = pairedProbability(result, metric, row.request.technology, column.request.technology);
          return <div className={probability == null ? "is-diagonal" : ""} key={column.request.technology}>
            {probability == null ? <span>—</span> : <><b>{percent(probability, 1)}</b><small>P({row.name} {symbol} {column.name})</small></>}
          </div>;
        })}
      </div>)}
    </div>
  </article>;
}

export function RiskPage({ results, jointResult, runState, onRun }) {
  const [tab, setTab] = useState("joint");
  const [sampleCount, setSampleCount] = useState("300");
  const [seed, setSeed] = useState("42");
  const hasResults = SCENARIOS.every((scenario) => results[scenario.id]);
  return (
    <div className="page-workspace">
      <Tabs label="Risk views" value={tab} onChange={setTab} items={[{ id: "joint", label: "Joint comparison" }, { id: "overview", label: "Risk overview" }, { id: "distributions", label: "Distributions" }, { id: "assumptions", label: "Simulation assumptions" }]} />
      <section className="risk-toolbar parallel-risk-toolbar"><div><p className="eyebrow">PAIRED SIMULATION DESIGN</p><strong>Solar + Wind + Wave in one sampled world</strong></div><Field label="Shared worlds" unit="1–20,000"><input type="number" min="1" max="20000" value={sampleCount} onChange={(event) => setSampleCount(event.target.value)} /></Field><Field label="Random seed" unit="reproducible"><input type="number" value={seed} onChange={(event) => setSeed(event.target.value)} /></Field><button className="primary-button" type="button" disabled={runState === "running"} onClick={() => onRun({ sampleCount: Number(sampleCount), seed: Number(seed) })}><Play size={15} weight="fill" />{runState === "running" ? "Sampling shared worlds…" : "Run paired uncertainty"}</button></section>
      {tab === "joint" && (jointResult ? <>
        <section className="joint-risk-intro"><div><p className="eyebrow">LEGITIMATE PAIRED PROBABILITIES</p><h2>Every comparison uses the same iteration.</h2></div><p>Tariff and discount rate are drawn once per economic world. Technology CAPEX, OPEX and annual resource sequences remain technology-specific.</p><dl><div><dt>Worlds</dt><dd>{number(jointResult.sample_count)}</dd></div><div><dt>Seed</dt><dd>{jointResult.random_seed ?? "Random"}</dd></div><div><dt>Paired tests</dt><dd>{jointResult.comparisons?.length || 0}</dd></div></dl></section>
        <section className="joint-matrix-grid"><JointProbabilityMatrix result={jointResult} metric="npv" /><JointProbabilityMatrix result={jointResult} metric="lcoe" /></section>
        <p className="joint-risk-note"><ShieldCheck size={16} />Each percentage is a within-world count over valid pairs; unrelated standalone iteration numbers are never matched.</p>
      </> : <div className="chart-placeholder tall"><ShieldCheck size={30} /><p>Run paired uncertainty to compare Solar, Wind, and Wave inside the same sampled economic worlds.</p></div>)}
      {tab === "overview" && (hasResults ? <section className="parallel-model-grid risk-model-grid">{SCENARIOS.map((scenario, index) => { const result = results[scenario.id]; const npv = result.metric_summaries?.find((item) => item.metric === "npv"); const lcoe = result.metric_summaries?.find((item) => item.metric === "lcoe"); const chart = riskHistogramOption(result.samples || [], "npv_usd", "USD", 1); return <article className="parallel-model-card chart-page-panel" key={scenario.id} style={{ "--model-color": scenario.color }}><header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>{result.sample_count} seeded samples</p></div><ShieldCheck size={22} /></header><div className="risk-key-metrics"><div><span>P(NPV &gt; 0)</span><strong>{percent(result.probability_npv_positive, 1)}</strong></div><div><span>Median NPV</span><strong>USD {number(npv?.median, 0)}</strong></div><div><span>P95 LCOE</span><strong>USD {number(lcoe?.percentile_95, 2)}/MWh</strong></div></div><ReactECharts option={chart} className="parallel-risk-chart" notMerge /></article>; })}</section> : <div className="chart-placeholder tall"><ShieldCheck size={30} /><p>Run all three seeded models to populate aligned risk statistics.</p></div>)}
      {tab === "distributions" && (hasResults ? <section className="parallel-model-grid chart-model-grid">{SCENARIOS.map((scenario, index) => { const result = results[scenario.id]; const chart = riskHistogramOption(result.samples || [], "lcoe_usd_per_mwh", "USD", 1); return <article className="parallel-model-card chart-page-panel" key={scenario.id} style={{ "--model-color": scenario.color }}><header className="parallel-model-header"><span>0{index + 1}</span><div><h2>{scenario.name}</h2><p>LCOE distribution</p></div><ChartLineUp size={21} /></header><ReactECharts option={chart} className="parallel-chart" notMerge /></article>; })}</section> : <div className="chart-placeholder tall"><ChartLineUp size={28} /><p>Run all three risk models first.</p></div>)}
      {tab === "assumptions" && <div className="formula-grid"><article><span>01 / REPRODUCIBILITY</span><h3>Fixed random seed</h3><code>seed = {seed}</code><p>Repeating the same inputs and seed returns the same simulation sequence.</p></article><article><span>02 / SHARED WORLD</span><h3>Correlated market setting</h3><code>tariff + discount rate</code><p>One draw is applied to Solar, Wind and Wave in each iteration. The shared tariff is centred on the mean of the three entered sale prices.</p></article><article><span>03 / TECHNOLOGY-SPECIFIC</span><h3>Independent project inputs</h3><code>CAPEX + OPEX + resource</code><p>Technology costs and empirical annual resource sequences are drawn separately. The API also accepts explicit performance uncertainties such as Wave efficiency.</p></article><article><span>04 / INTERPRETATION</span><h3>Paired decision statistics</h3><code>P(NPVsolar &gt; NPVwind)</code><p>Probabilities compare results only within the same sampled world. Climate trend, serial correlation and cross-resource weather dependence are not modelled.</p></article></div>}
    </div>
  );
}

export function MethodologyPage({ version = "1.1.0" }) {
  const [tab, setTab] = useState("chain");
  return <div className="page-workspace"><Tabs label="Methodology sections" value={tab} onChange={setTab} items={[{ id: "chain", label: "Model chain" }, { id: "equations", label: "Core equations" }, { id: "boundaries", label: "What the model does not claim" }]} />
    {tab === "chain" && <section className="method-chain"><header><p className="eyebrow">METHODOLOGY {version}</p><h2>A dependency-aware calculation, not a spreadsheet of shortcuts.</h2></header><ol>{["Location & provider resolution", "Historical resource record", "Technology physics at each interval", "Annual integration and completeness", "Empirical P90 / P50 / P10", "Lifecycle and degradation", "Unlevered project cash flows", "Sensitivity, break-even and risk"].map((step, index) => <li key={step}><span>{String(index + 1).padStart(2, "0")}</span><strong>{step}</strong><p>{index < 3 ? "Upstream physical evidence is preserved with source and coordinate metadata." : "Downstream calculations reuse validated upstream work whenever the dependency graph allows it."}</p></li>)}</ol></section>}
    {tab === "equations" && <div className="formula-grid"><article><span>SOLAR</span><h3>PV output</h3><code>P = Pr(G/Gr)fT(1-L)</code><p>Rated electrical capacity is not multiplied by panel efficiency again.</p></article><article><span>WIND</span><h3>Tabulated power curve</h3><code>P(v) = linear interpolation</code><p>The bundled NLR/IEA 3.4 MW curve is the default; cubic output is an explicit fallback only.</p></article><article><span>WAVE</span><h3>Deep-water flux</h3><code>J = ρg²Hs²Te / 64π</code><p>Wave power per metre is converted to capped device output using capture width and efficiency.</p></article><article><span>FINANCE</span><h3>Levelized cost</h3><code>LCOE = PV(costs) / PV(energy)</code><p>Electricity sale price affects project value, not LCOE.</p></article></div>}
    {tab === "boundaries" && <section className="boundaries-grid"><article><h3>Screening, not final design</h3><p>No grid dispatch, wake model, structural design, CFD, debt or tax model is implied.</p></article><article><h3>Wave remains research-grade</h3><p>Device economics are explicit scenarios. Constant capture width and efficiency do not replace a certified power matrix.</p></article><article><h3>Historical data are not measurements</h3><p>Reanalysis grid cells can smooth local extremes. Site campaigns remain necessary before investment.</p></article><article><h3>Risk is conditional</h3><p>The IID annual bootstrap does not model climate change, cycles or serial correlation.</p></article></section>}
  </div>;
}

export function SourcesPage({ assumptions, market, onExport }) {
  const references = assumptions ? Object.entries(assumptions) : [];
  return <div className="page-workspace sources-page"><section className="source-hero"><div><p className="eyebrow">EVIDENCE REGISTER</p><h2>Every number should have a provenance trail.</h2><p>Measured/site data, published benchmarks, scenario assumptions and user inputs are kept distinct.</p></div><button className="secondary-button" type="button" onClick={onExport}><DownloadSimple size={15} />Export evidence pack</button></section><div className="source-register"><article><header><Database size={20} /><div><h3>Historical resource providers</h3><p>Coordinate-based physical inputs</p></div></header><dl><div><dt>Solar & wind</dt><dd>Open-Meteo Historical / ERA5-derived series</dd></div><div><dt>Wind power curve</dt><dd>NLR/IEA Reference 3.4 MW, tabulated</dd></div><div><dt>Wave</dt><dd>Copernicus Marine preferred; Open-Meteo marine fallback</dd></div><div><dt>Record</dt><dd>{market?.resource_period || "2015–2024"}</dd></div></dl></article><article><header><CurrencyDollar size={20} /><div><h3>Current cost and currency context</h3><p>Dated, not silently rebased</p></div></header><dl><div><dt>Cost basis</dt><dd>{market?.cost_basis_label}</dd></div><div><dt>FX</dt><dd>USD/PKR {number(market?.fx?.rate, 4)}</dd></div><div><dt>As of</dt><dd>{market?.fx?.as_of ? new Date(market.fx.as_of).toLocaleDateString("en-GB", { timeZone: "UTC" }) : "—"}</dd></div></dl></article></div><section className="editorial-panel"><header className="panel-heading"><div><span>01</span><h2>Technology assumption catalogue</h2></div><BookOpenText size={20} /></header>{references.length ? <div className="assumption-cards">{references.map(([technology, reference]) => <article key={technology}><h3>{technology}</h3><p>{reference.description || "Published and explicit model inputs for this technology."}</p><small>Available through the local assumptions API and evidence export.</small></article>)}</div> : <p className="panel-intro">Loading the assumption register from the Python API…</p>}</section></div>;
}
