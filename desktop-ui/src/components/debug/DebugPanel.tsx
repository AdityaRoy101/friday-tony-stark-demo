import type { FridayDebugState } from '../../lib/types';
import { formatTimestamp } from '../../lib/utils';

interface DebugPanelProps {
  debug: FridayDebugState;
}

function MetricRow({ label, value }: { label: string; value?: number }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-zinc-500">{label}</span>
      <span className={value === undefined ? 'text-zinc-600' : 'text-cyan-300'}>
        {value === undefined ? '-' : `${value.toFixed(0)}ms`}
      </span>
    </div>
  );
}

function eventMessage(data: unknown): string {
  if (typeof data !== 'object' || data === null) {
    return String(data);
  }

  const value = data as Record<string, unknown>;
  const event = String(value.event ?? 'event');
  if (typeof value.transcript === 'string') {
    return `${event}: ${value.transcript}`;
  }
  if (typeof value.text === 'string' && value.text) {
    return `${event}: ${value.text}`;
  }
  if (Array.isArray(value.tools)) {
    const tools = value.tools
      .map((tool) => (typeof tool === 'object' && tool !== null ? String((tool as { name?: string }).name ?? 'tool') : 'tool'))
      .join(', ');
    return `${event}: ${tools}`;
  }
  if (typeof value.error === 'string') {
    return `${event}: ${value.error}`;
  }
  if (typeof value.newState === 'string') {
    return `${event}: ${value.newState}`;
  }
  return event;
}

export default function DebugPanel({ debug }: DebugPanelProps) {
  const hasTranscript = debug.partialTranscript || debug.finalTranscript;

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="text-sm font-semibold text-zinc-200">Latency</h3>
        <div className="mt-2 space-y-1 text-xs">
          <MetricRow label="STT final" value={debug.latency.transcriptionDelayMs} />
          <MetricRow label="Turn end" value={debug.latency.endOfTurnDelayMs} />
          <MetricRow label="LLM first token" value={debug.latency.llmFirstTokenMs} />
          <MetricRow label="TTS first audio" value={debug.latency.ttsFirstAudioMs} />
          <MetricRow label="End to response" value={debug.latency.e2eLatencyMs} />
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-zinc-200">Live State</h3>
        <div className="mt-2 space-y-1 text-xs">
          <div className="flex justify-between gap-3">
            <span className="text-zinc-500">Agent</span>
            <span className="text-zinc-300">{debug.agentState || 'waiting'}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-zinc-500">User</span>
            <span className="text-zinc-300">{debug.userState || 'waiting'}</span>
          </div>
        </div>
      </div>

      {hasTranscript && (
        <div>
          <h3 className="text-sm font-semibold text-zinc-200">Transcript</h3>
          <p className="mt-2 rounded border border-zinc-800 bg-zinc-950 p-2 text-xs text-zinc-300">
            {debug.partialTranscript || debug.finalTranscript}
          </p>
        </div>
      )}

      {debug.lastError && (
        <div className="rounded border border-red-900 bg-red-950/30 p-2 text-xs text-red-200">
          {debug.lastError}
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold text-zinc-200">Event Log</h3>
        <div className="mt-2 max-h-56 space-y-1 overflow-auto rounded border border-zinc-800 bg-zinc-950 p-2">
          {debug.events.length === 0 && (
            <div className="text-xs text-zinc-600">Waiting for Friday telemetry...</div>
          )}
          {debug.events.slice(0, 30).map((event) => (
            <div key={event.id} className="grid grid-cols-[72px_1fr] gap-2 text-xs">
              <span className="text-zinc-600">{formatTimestamp(event.timestamp)}</span>
              <span
                className={
                  event.type === 'error'
                    ? 'text-red-300'
                    : event.type === 'warn'
                      ? 'text-yellow-300'
                      : 'text-zinc-400'
                }
              >
                {eventMessage(event.data)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

