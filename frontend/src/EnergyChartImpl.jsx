import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  AriaComponent,
  BarChart,
  CanvasRenderer,
  GridComponent,
  HeatmapChart,
  LabelLayout,
  LegendComponent,
  LineChart,
  MarkLineComponent,
  MarkPointComponent,
  ScatterChart,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
]);

export default function EnergyChartImpl(props) {
  return <ReactEChartsCore echarts={echarts} {...props} />;
}
