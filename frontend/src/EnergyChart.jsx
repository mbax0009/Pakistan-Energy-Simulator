import { lazy, Suspense } from "react";

const EnergyChartImpl = lazy(() => import("./EnergyChartImpl.jsx"));

export default function EnergyChart(props) {
  return (
    <Suspense
      fallback={(
        <div
          aria-label="Loading chart"
          className={props.className}
          role="status"
        />
      )}
    >
      <EnergyChartImpl {...props} />
    </Suspense>
  );
}
