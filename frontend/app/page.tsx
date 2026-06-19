"use client";

import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import UploadZone from "@/components/UploadZone";
import MaterialsList from "@/components/MaterialsList";

export default function Home() {
  const [materialsRefresh, setMaterialsRefresh] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function handleUploadSuccess() {
    setMaterialsRefresh((p) => p + 1);
  }

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center justify-between gap-2.5 border-b border-border px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-accent/10 text-lg">
            🎓
          </span>
          <div>
            <h1 className="text-sm font-semibold leading-tight">
              AI Study Buddy
            </h1>
            <p className="text-xs text-muted">Your personal AI tutor</p>
          </div>
        </div>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="rounded-lg p-1.5 hover:bg-card md:hidden"
          title="Toggle materials panel"
        >
          📚
        </button>
      </header>

      <div className="flex min-h-0 flex-1 gap-0 md:gap-px">
        <main className="min-h-0 flex-1 md:border-r md:border-border">
          <ChatWindow />
        </main>

        <aside
          className={`fixed right-0 top-[57px] z-10 h-[calc(100%-57px)] w-80 overflow-y-auto border-l border-border bg-background p-5 transition-transform md:static md:z-0 md:h-auto md:w-80 md:flex-shrink-0 md:transform-none ${
            sidebarOpen ? "translate-x-0" : "translate-x-full md:translate-x-0"
          }`}
        >
          <div className="space-y-6">
            <UploadZone onUploadSuccess={handleUploadSuccess} />

            <div className="border-t border-border pt-4">
              <h2 className="text-sm font-semibold mb-3">Uploaded Files</h2>
              <MaterialsList refreshTrigger={materialsRefresh} />
            </div>
          </div>
        </aside>

        {sidebarOpen && (
          <div
            className="fixed inset-0 z-[5] bg-black/20 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </div>
    </div>
  );
}
