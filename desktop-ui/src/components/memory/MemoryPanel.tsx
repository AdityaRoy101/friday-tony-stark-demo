import { useEffect, useState } from 'react';
import type { MemoryItem, MemoryResponse } from '../../lib/types';

export default function MemoryPanel() {
  const [memory, setMemory] = useState<MemoryResponse>({ path: '', items: [] });
  const [draft, setDraft] = useState<MemoryItem>({ key: '', value: '', category: 'general' });
  const [error, setError] = useState<string | null>(null);

  const loadMemory = async () => {
    try {
      setError(null);
      setMemory(await window.fridayLiveKit.getMemory());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    void loadMemory();
  }, []);

  const save = async () => {
    try {
      setError(null);
      const updated = await window.fridayLiveKit.saveMemoryItem(draft);
      setMemory(updated);
      setDraft({ key: '', value: '', category: 'general' });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const forget = async (key: string) => {
    try {
      setError(null);
      setMemory(await window.fridayLiveKit.forgetMemoryItem(key));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">Memory</h3>
        <button
          type="button"
          onClick={() => void loadMemory()}
          className="rounded border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:border-cyan-500 hover:text-cyan-300"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-900 bg-red-950/30 p-2 text-xs text-red-200">
          {error}
        </div>
      )}

      <div className="grid gap-2">
        <input
          value={draft.key}
          onChange={(event) => setDraft((current) => ({ ...current, key: event.target.value }))}
          placeholder="Key"
          className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-cyan-600"
        />
        <input
          value={draft.value}
          onChange={(event) => setDraft((current) => ({ ...current, value: event.target.value }))}
          placeholder="Value"
          className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-cyan-600"
        />
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <input
            value={draft.category}
            onChange={(event) => setDraft((current) => ({ ...current, category: event.target.value }))}
            placeholder="Category"
            className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs text-zinc-200 outline-none focus:border-cyan-600"
          />
          <button
            type="button"
            onClick={() => void save()}
            disabled={!draft.key.trim() || !draft.value.trim()}
            className="rounded border border-cyan-700 px-3 py-1 text-xs text-cyan-200 hover:bg-cyan-950 disabled:cursor-not-allowed disabled:border-zinc-800 disabled:text-zinc-600"
          >
            Save
          </button>
        </div>
      </div>

      <div className="max-h-48 space-y-2 overflow-auto rounded border border-zinc-800 bg-zinc-950 p-2">
        {memory.items.length === 0 && (
          <div className="text-xs text-zinc-600">No visible memory yet.</div>
        )}
        {memory.items.map((item) => (
          <div key={item.key} className="rounded border border-zinc-900 bg-zinc-900/50 p-2">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-xs font-semibold text-zinc-200">{item.key}</div>
                <div className="mt-1 break-words text-xs text-zinc-400">{item.value}</div>
                <div className="mt-1 text-[11px] text-zinc-600">{item.category || 'general'}</div>
              </div>
              <button
                type="button"
                onClick={() => void forget(item.key)}
                className="shrink-0 rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-400 hover:border-red-800 hover:text-red-300"
              >
                Forget
              </button>
            </div>
          </div>
        ))}
      </div>

      {memory.path && (
        <div className="break-all text-[11px] text-zinc-700">{memory.path}</div>
      )}
    </div>
  );
}

