import { useEffect, useRef } from "react";
import type uPlot from "uplot";
import type { Plot } from "../contracts";

const COLOURS = ["#0f6e56", "#185fa5", "#993c1d", "#5f5e5a"];

/** Series that share no x values are merged onto one x axis (null where a series has no point). */
export function alignSeries(plot: Plot): { names: string[]; data: (number | null)[][] } {
  const names = Object.keys(plot.series);
  const xs = [...new Set(names.flatMap((n) => plot.series[n]!.map(([t]) => t)))].sort((a, b) => a - b);
  const index = new Map(xs.map((x, i) => [x, i]));
  const ys = names.map((n) => {
    const col: (number | null)[] = new Array(xs.length).fill(null);
    for (const [t, v] of plot.series[n]!) col[index.get(t)!] = v;
    return col;
  });
  return { names, data: [xs, ...ys] };
}

/** A check's plot (time in ms on x). Never a pulse waveform: the contract forbids family A plots. */
export function CheckPlot({ plot, title }: { plot: Plot; title: string }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = host.current;
    if (!el || typeof window.matchMedia !== "function") return; // no canvas in unit tests
    let chart: uPlot | null = null;
    let alive = true;
    // uPlot reads matchMedia when it loads, so it is loaded only when a plot is drawn (also keeps it out of the
    // customer pages' bundle).
    void Promise.all([import("uplot"), import("uplot/dist/uPlot.min.css")]).then(([{ default: UPlot }]) => {
      if (!alive) return;
      chart = draw(UPlot, el, plot);
    });
    return () => {
      alive = false;
      chart?.destroy();
    };
  }, [plot]);
  return <div className="plot" ref={host} role="img" aria-label={`Plot of ${title}`} />;
}

function draw(UPlot: typeof uPlot, el: HTMLElement, plot: Plot): uPlot {
  const { names, data } = alignSeries(plot);
  const chart = new UPlot(
    {
      width: Math.max(280, el.clientWidth || 560),
      height: 200,
      scales: { x: { time: false } },
      axes: [{ label: "ms" }, {}],
      series: [{}, ...names.map((n, k) => ({ label: n, stroke: COLOURS[k % COLOURS.length], spanGaps: true }))],
    },
    data as uPlot.AlignedData,
    el,
  );
  for (const [t, label] of plot.markers ?? []) {
    const left = chart.valToPos(t, "x");
    const mark = document.createElement("span");
    mark.className = "plot-marker";
    mark.style.left = `${left}px`;
    mark.title = label;
    chart.over.appendChild(mark);
  }
  return chart;
}
