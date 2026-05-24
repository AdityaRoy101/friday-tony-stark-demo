interface PlaygroundHeaderProps {
  connectionState: string;
  roomName: string;
  agentState?: string;
  mode?: string;
  onDisconnect: () => void;
}

export default function PlaygroundHeader({
  connectionState,
  roomName,
  agentState,
  mode,
  onDisconnect,
}: PlaygroundHeaderProps) {
  const isConnected = connectionState === 'connected';

  return (
    <header className="min-h-14 border-b border-zinc-800 bg-zinc-950/95 flex items-center justify-between gap-4 px-4 py-3 shrink-0">
      <div className="min-w-0 flex flex-wrap items-center gap-x-4 gap-y-2">
        <h1 className="text-base font-semibold text-white">Friday Playground</h1>
        <div className="flex items-center gap-2 rounded-full border border-zinc-800 px-2.5 py-1">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-zinc-600'}`} />
          <span className="text-xs font-medium text-zinc-300">
            {isConnected ? 'Connected' : connectionState}
          </span>
        </div>
        {agentState && (
          <div className="rounded-full border border-cyan-950 bg-cyan-950/30 px-2.5 py-1 text-xs font-medium text-cyan-200">
            Agent {agentState}
          </div>
        )}
        {mode && (
          <div className="rounded-full border border-zinc-800 px-2.5 py-1 text-xs text-zinc-400">
            {mode}
          </div>
        )}
      </div>

      <div className="min-w-0 flex items-center gap-3">
        <span className="hidden max-w-[360px] truncate text-sm text-zinc-500 md:inline">
          {roomName}
        </span>
        <button
          onClick={onDisconnect}
          className="px-4 py-1.5 text-sm font-medium rounded border border-zinc-700 text-zinc-300 hover:bg-zinc-800 transition-colors"
        >
          Disconnect
        </button>
      </div>
    </header>
  );
}
