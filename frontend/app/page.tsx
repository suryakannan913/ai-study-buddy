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
    <div className="flex h-dvh flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 px-4 py-4 backdrop-blur-sm md:px-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent/70 text-xl shadow-md">
              🎓
            </div>
            <div>
              <h1 className="text-lg font-bold text-foreground">
                AI Study Buddy
              </h1>
              <p className="text-xs text-muted-foreground">Learn smarter with RAG</p>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="inline-flex items-center justify-center rounded-lg p-2 hover:bg-accent/10 transition-colors md:hidden"
            title="Toggle materials panel"
          >
            <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </header>

      {/* Main Layout */}
      <div className="flex min-h-0 flex-1 gap-0">
        {/* Chat Area */}
        <main className="min-h-0 flex-1 overflow-hidden md:border-r md:border-border/50">
          <ChatWindow />
        </main>

        {/* Sidebar */}
        <aside
          className={`fixed right-0 top-[72px] z-10 h-[calc(100%-72px)] w-80 overflow-y-auto border-l border-border/50 bg-card/50 p-6 shadow-lg backdrop-blur-sm transition-all duration-300 ease-in-out md:static md:z-0 md:h-auto md:w-96 md:flex-shrink-0 md:shadow-none ${
            sidebarOpen ? "translate-x-0" : "translate-x-full md:translate-x-0"
          }`}
        >
          <div className="space-y-8">
            <div>
              <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Upload Materials</h2>
              <UploadZone onUploadSuccess={handleUploadSuccess} />
            </div>

            <div className="border-t border-border/50 pt-6">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Your Files</h2>
              <MaterialsList refreshTrigger={materialsRefresh} />
            </div>
          </div>
        </aside>

        {/* Mobile Overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-[9] bg-black/30 backdrop-blur-sm transition-opacity md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </div>
    </div>
  );
}
