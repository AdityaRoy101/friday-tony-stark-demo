import type { ReactNode } from 'react';

interface PlaygroundTileProps {
  title: string;
  children: ReactNode;
  className?: string;
}

export default function PlaygroundTile({ title, children, className = '' }: PlaygroundTileProps) {
  return (
    <div className={`flex min-h-0 flex-col overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950 ${className}`}>
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3 text-sm font-medium text-zinc-300">
        <span>{title}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-4">
        {children}
      </div>
    </div>
  );
}
