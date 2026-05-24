import { useState } from 'react';

interface AttributesInspectorProps {
  attributes: Record<string, string>;
  onUpdate?: (attributes: Record<string, string>) => void;
}

export default function AttributesInspector({ attributes, onUpdate }: AttributesInspectorProps) {
  const [editing, setEditing] = useState(false);
  const [jsonString, setJsonString] = useState(() => JSON.stringify(attributes, null, 2));

  const handleApply = () => {
    try {
      const parsed = JSON.parse(jsonString);
      onUpdate?.(parsed);
      setEditing(false);
    } catch (error) {
      console.error('Invalid participant attributes JSON', error);
    }
  };

  return (
    <div className="text-sm">
      <div className="flex justify-between items-center mb-2">
        <span className="text-zinc-500">Attributes</span>
        {!editing && (
          <button
            className="text-xs text-indigo-400 hover:text-indigo-300"
            onClick={() => setEditing(true)}
          >
            Edit
          </button>
        )}
      </div>

      {editing ? (
        <div className="space-y-2">
          <textarea
            className="min-h-[80px] w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 font-mono text-xs text-zinc-100 placeholder:text-zinc-500 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={jsonString}
            onChange={(e) => setJsonString(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              className="px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700"
              onClick={handleApply}
            >
              Apply
            </button>
            <button
              className="px-3 py-1 text-xs border border-zinc-700 text-zinc-400 rounded hover:bg-zinc-800"
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <pre className="text-xs text-zinc-400 bg-zinc-900 p-2 rounded overflow-auto max-h-32">
          {JSON.stringify(attributes, null, 2)}
        </pre>
      )}
    </div>
  );
}
