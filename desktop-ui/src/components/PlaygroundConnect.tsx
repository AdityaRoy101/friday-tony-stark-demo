import { useState, useEffect } from 'react';
import type { ConnectionConfig } from '../lib/types';

interface PlaygroundConnectProps {
  onConnect: (config: ConnectionConfig) => void;
}

export default function PlaygroundConnect({ onConnect }: PlaygroundConnectProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusText, setStatusText] = useState('Preparing LiveKit connection...');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const autoConnect = async () => {
      setIsLoading(true);
      setError('');
      setStatusText('Preparing LiveKit connection...');

      try {
        if (!window.fridayLiveKit) {
          throw new Error('Friday desktop bridge is unavailable. Open this UI through Electron, not a plain browser tab.');
        }

        const env = await window.fridayLiveKit.getEnv();
        if (cancelled) {
          return;
        }

        setStatusText(
          env.livekitMode === 'local'
            ? `Connecting to local LiveKit at ${env.livekitUrl}...`
            : 'Connecting to LiveKit Cloud...',
        );

        const roomInfo = await window.fridayLiveKit.getOrCreateRoom();
        if (cancelled) {
          return;
        }

        const participantName = env.participantName || 'User';
        const participantIdentity = 'user-' + Math.random().toString(36).substring(2, 8);

        const result = await window.fridayLiveKit.createToken({
          roomName: roomInfo.roomName,
          participantName,
          participantIdentity,
          agentName: env.agentName || undefined,
        });
        if (cancelled) {
          return;
        }

        const config: ConnectionConfig = {
          mode: env.livekitMode,
          serverUrl: result.serverUrl,
          token: result.participantToken,
          roomName: roomInfo.roomName,
          participant: {
            identity: participantIdentity,
            name: participantName,
          },
          agentName: env.agentName || undefined,
        };

        onConnect(config);
      } catch (err) {
        console.error('Auto-connect failed:', err);
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to auto-connect');
        setIsLoading(false);
      }
    };

    autoConnect();
    return () => {
      cancelled = true;
    };
  }, [onConnect, attempt]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full w-full">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-zinc-400 text-sm">{statusText}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-full w-full p-4">
      <div className="w-full max-w-md">
        <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-white mb-2">Connect to playground</h1>
            <p className="text-zinc-400 text-sm">
              Connect to a LiveKit room to interact with an agent.
            </p>
          </div>

          {error && (
            <div className="p-3 bg-red-950/30 border border-red-900 rounded text-red-400 text-sm">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={() => setAttempt((current) => current + 1)}
            className="mt-4 w-full rounded-md border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 transition-colors hover:border-cyan-500 hover:text-cyan-200"
          >
            Retry connection
          </button>
        </div>
      </div>
    </div>
  );
}
