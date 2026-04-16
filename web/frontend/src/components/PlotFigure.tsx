import * as Plot from "@observablehq/plot";
import { useEffect, useRef } from "react";

interface PlotFigureProps {
  options: Plot.PlotOptions;
}

export default function PlotFigure({ options }: PlotFigureProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (options === undefined) return;
    const plot = Plot.plot(options);
    containerRef.current?.append(plot);
    return () => plot.remove();
  }, [options]);

  return <div ref={containerRef} className="w-full overflow-hidden" />;
}
