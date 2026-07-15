"use client";

import mermaid from "mermaid";
import { useEffect, useRef } from "react";

mermaid.initialize({
  startOnLoad: false,
  theme: "neutral",
  suppressErrorRendering: true,
  flowchart: {
    useMaxWidth: true,
    nodeSpacing: 80,
    rankSpacing: 120,
  },
});

type MermaidDiagramProps = {
  chart: string;
};

export default function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    async function renderDiagram() {
      if (!containerRef.current) return;

      try {
        await mermaid.parse(chart);

        const id = `mermaid-${crypto.randomUUID()}`;
        const { svg } = await mermaid.render(id, chart);

        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = svg;

        const svgElement = containerRef.current.querySelector("svg");

        if (svgElement) {
          svgElement.style.display = "block";
          svgElement.style.margin = "0 auto";
          svgElement.style.maxWidth = "100%";
          svgElement.style.height = "auto";
          svgElement.setAttribute("preserveAspectRatio", "xMidYMid meet");
        }
      } catch (error) {
        console.error("Mermaid render error:", error);

        if (containerRef.current) {
          containerRef.current.innerHTML = `
            <div class="flex h-64 items-center justify-center rounded-xl border border-red-200 bg-red-50 text-red-600">
              Failed to render diagram.
            </div>
          `;
        }
      }
    }

    renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [chart]);

  return (
    <div
      ref={containerRef}
      className="flex w-full items-center justify-center overflow-auto"
    />
  );
}
