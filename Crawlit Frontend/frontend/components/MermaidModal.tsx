"use client";

import { X, Maximize2 } from "lucide-react";
import MermaidDiagram from "./MermaidDiagram";
import { useState } from "react";

export default function MermaidModal({ chart }: { chart: string }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Preview */}
      <div
        onClick={() => setOpen(true)}
        className="group relative w-full cursor-zoom-in"
      >
        <div className="absolute right-4 top-4 z-10 rounded-xl bg-white/90 p-2 opacity-0 shadow transition group-hover:opacity-100">
          <Maximize2 size={18} />
        </div>

        <div className="flex min-h-[30rem] items-center justify-center overflow-auto rounded-2xl border border-stone-100 bg-stone-50 p-6">
          <div className="w-full">
            <MermaidDiagram chart={chart} />
          </div>
        </div>
      </div>

      {/* Fullscreen */}
      {open && (
        <div className="fixed inset-0 z-100 bg-black/60 backdrop-blur-sm">
          <div className="flex h-full w-full items-center justify-center p-8">
            <div className="relative h-[90vh] w-[95vw] rounded-3xl bg-white shadow-2xl">
              <button
                onClick={() => setOpen(false)}
                className="absolute right-5 top-5 z-20 rounded-xl border bg-white p-2 hover:bg-stone-100"
              >
                <X />
              </button>

              <div className="h-full overflow-auto p-8">
                <MermaidDiagram chart={chart} />
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
