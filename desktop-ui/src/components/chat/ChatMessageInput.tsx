import { useState } from 'react';

interface ChatMessageInputProps {
  onSend: (message: string) => void | Promise<void>;
  disabled?: boolean;
}

export default function ChatMessageInput({ onSend, disabled = false }: ChatMessageInputProps) {
  const [input, setInput] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      try {
        setError('');
        await onSend(input.trim());
        setInput('');
      } catch (err) {
        console.error('Failed to send chat message', err);
        setError(err instanceof Error ? err.message : 'Failed to send message');
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="shrink-0 border-t border-zinc-800 p-3">
      <div className="flex gap-2">
        <input
          type="text"
          className="min-w-0 flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={disabled}
        />
        <button
          type="submit"
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50"
          disabled={disabled || !input.trim()}
        >
          Send
        </button>
      </div>
      {error && <div className="mt-2 text-xs text-red-300">{error}</div>}
    </form>
  );
}
