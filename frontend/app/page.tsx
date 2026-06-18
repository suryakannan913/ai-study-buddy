import ChatWindow from "@/components/ChatWindow";

export default function Home() {
  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-2.5 border-b border-border px-5 py-3.5">
        <span className="flex size-8 items-center justify-center rounded-lg bg-accent/10 text-lg">
          🎓
        </span>
        <div>
          <h1 className="text-sm font-semibold leading-tight">
            AI Study Buddy
          </h1>
          <p className="text-xs text-muted">Your personal AI tutor</p>
        </div>
      </header>
      <main className="min-h-0 flex-1">
        <ChatWindow />
      </main>
    </div>
  );
}
