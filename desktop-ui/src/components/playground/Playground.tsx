import { useCallback, useEffect, useState } from 'react';
import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  StartAudio,
  useConnectionState,
  useRoomContext,
  useVoiceAssistant,
} from '@livekit/components-react';
import { ConnectionState, DisconnectReason } from 'livekit-client';
import type { MediaDeviceFailure } from 'livekit-client';
import type { ConnectionConfig } from '../../lib/types';
import { useFridayDebug } from '../../hooks/useFridayDebug';
import PlaygroundHeader from './PlaygroundHeader';
import PlaygroundTile from './PlaygroundTile';
import ChatTile from '../chat/ChatTile';
import DebugPanel from '../debug/DebugPanel';
import MemoryPanel from '../memory/MemoryPanel';

interface PlaygroundProps {
  config: ConnectionConfig;
  onConnected: () => void;
  onDisconnect: () => void;
}

function PlaygroundContent({ config, onConnected, onDisconnect }: PlaygroundProps) {
  const [activeTab, setActiveTab] = useState<'chat' | 'voice' | 'settings'>('chat');
  const [error, setError] = useState<string | null>(null);
  const [hasEverConnected, setHasEverConnected] = useState(false);
  const room = useRoomContext();
  const connectionState = useConnectionState();
  const voiceAssistant = useVoiceAssistant();
  const fridayDebug = useFridayDebug();

  useEffect(() => {
    if (connectionState === ConnectionState.Connected) {
      setHasEverConnected(true);
      onConnected();
      setError(null);
    } else if (connectionState === ConnectionState.Disconnected && hasEverConnected) {
      setError((currentError) => currentError ?? 'Disconnected from room');
    }
  }, [connectionState, hasEverConnected, onConnected]);

  const handleDisconnect = () => {
    setError(null);
    room.disconnect();
    onDisconnect();
  };

  return (
    <div className="flex flex-col h-full">
      <PlaygroundHeader
        connectionState={connectionState}
        roomName={config.roomName}
        mode={config.mode}
        agentState={fridayDebug.agentState || voiceAssistant.state}
        onDisconnect={handleDisconnect}
      />

      {error && (
        <div className="mx-4 mt-4 p-3 bg-red-950/50 border border-red-900 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-hidden">
        <div className="hidden h-full p-3 md:grid md:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.9fr)] md:gap-3 lg:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.85fr)] lg:gap-4 lg:p-4">
          <div className="flex h-full min-h-0 flex-col">
            <PlaygroundTile title="Chat" className="flex-1 min-h-0">
              <ChatTile connectionState={connectionState} debug={fridayDebug} />
            </PlaygroundTile>
          </div>

          <div className="flex h-full min-h-0 flex-col gap-3 lg:gap-4">
            <PlaygroundTile title="Voice" className="min-h-[236px]">
              <VoicePanel
                connectionState={connectionState}
                agentState={voiceAssistant.state}
                debug={fridayDebug}
              />
            </PlaygroundTile>

            <PlaygroundTile title="Session" className="flex-1 min-h-0">
              <SettingsContent
                config={config}
                connectionState={connectionState}
                agentIdentity={voiceAssistant.agent?.identity}
                agentState={voiceAssistant.state}
                debug={fridayDebug}
              />
            </PlaygroundTile>
          </div>
        </div>

        <div className="flex h-full flex-col md:hidden">
          <div className="flex border-b border-zinc-800">
            {(['chat', 'voice', 'settings'] as const).map((tab) => (
              <button
                key={tab}
                className={`flex-1 py-3 text-sm font-medium capitalize ${
                  activeTab === tab
                    ? 'text-indigo-400 border-b-2 border-indigo-400'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-auto p-4">
            {activeTab === 'voice' && (
              <VoicePanel
                connectionState={connectionState}
                agentState={voiceAssistant.state}
                debug={fridayDebug}
              />
            )}
            {activeTab === 'chat' && <ChatTile connectionState={connectionState} debug={fridayDebug} />}
            {activeTab === 'settings' && (
              <SettingsContent
                config={config}
                connectionState={connectionState}
                agentIdentity={voiceAssistant.agent?.identity}
                agentState={voiceAssistant.state}
                debug={fridayDebug}
              />
            )}
          </div>
        </div>
      </div>

      <RoomAudioRenderer />
      <StartAudio label="Allow audio playback" />
    </div>
  );
}

function AgentAudioVisualizer() {
  const { audioTrack, state } = useVoiceAssistant();

  if (!audioTrack) {
    return (
      <div className="flex h-32 flex-col items-center justify-center gap-2 text-zinc-600 text-sm">
        <span>Waiting for agent audio...</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center w-full h-32 [--lk-va-bar-width:22px] [--lk-va-bar-gap:14px] [--lk-fg:#22d3ee]">
      <BarVisualizer
        state={state}
        trackRef={audioTrack}
        barCount={5}
        options={{ minHeight: 20 }}
      />
    </div>
  );
}

function StatusPill({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: 'neutral' | 'good' | 'active' | 'warn';
}) {
  const toneClass = {
    neutral: 'border-zinc-800 bg-zinc-900/70 text-zinc-300',
    good: 'border-emerald-900 bg-emerald-950/40 text-emerald-200',
    active: 'border-cyan-900 bg-cyan-950/40 text-cyan-200',
    warn: 'border-amber-900 bg-amber-950/40 text-amber-200',
  }[tone];

  return (
    <div className={`rounded-lg border px-3 py-2 ${toneClass}`}>
      <div className="text-[11px] uppercase tracking-wide opacity-60">{label}</div>
      <div className="mt-1 truncate text-sm font-medium">{value}</div>
    </div>
  );
}

function VoicePanel({
  connectionState,
  agentState,
  debug,
}: {
  connectionState: ConnectionState;
  agentState: string;
  debug: ReturnType<typeof useFridayDebug>;
}) {
  const displayAgentState = debug.agentState || agentState || 'waiting';
  const displayUserState = debug.userState || 'waiting';
  const transcript = debug.partialTranscript || debug.finalTranscript || '';

  return (
    <div className="flex h-full min-h-[220px] flex-col gap-4">
      <div className="grid grid-cols-2 gap-2">
        <StatusPill
          label="Room"
          value={connectionState === ConnectionState.Connected ? 'connected' : connectionState}
          tone={connectionState === ConnectionState.Connected ? 'good' : 'warn'}
        />
        <StatusPill
          label="Agent"
          value={displayAgentState}
          tone={displayAgentState === 'speaking' ? 'active' : displayAgentState === 'listening' ? 'good' : 'neutral'}
        />
        <StatusPill
          label="User"
          value={displayUserState}
          tone={displayUserState === 'speaking' ? 'active' : 'neutral'}
        />
        <StatusPill
          label="STT"
          value={debug.latency.transcriptionDelayMs ? `${debug.latency.transcriptionDelayMs.toFixed(0)}ms` : 'waiting'}
          tone={debug.latency.transcriptionDelayMs ? 'good' : 'neutral'}
        />
      </div>

      <div className="rounded-lg border border-zinc-800 bg-black/40 p-3">
        <AgentAudioVisualizer />
      </div>

      <div className="min-h-[92px] rounded-lg border border-zinc-800 bg-zinc-950 p-3">
        <div className="text-xs font-medium text-zinc-500">Live transcript</div>
        <div className="mt-2 text-sm leading-6 text-zinc-200">
          {transcript || <span className="text-zinc-600">Waiting for speech...</span>}
        </div>
      </div>
    </div>
  );
}

function SettingsContent({
  config,
  connectionState,
  agentIdentity,
  agentState,
  debug,
}: {
  config: ConnectionConfig;
  connectionState: ConnectionState;
  agentIdentity?: string;
  agentState: string;
  debug: ReturnType<typeof useFridayDebug>;
}) {
  return (
    <div className="h-full space-y-5 overflow-auto pr-1 text-sm">
      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-zinc-200">Session</h3>
        <div className="flex justify-between">
          <span className="text-zinc-500">Mode</span>
          <span className={config.mode === 'local' ? 'text-cyan-400' : 'text-zinc-300'}>
            {config.mode}
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-zinc-500">Server</span>
          <span className="text-right text-xs text-zinc-300 break-all">{config.serverUrl}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-zinc-500">Room</span>
          <span className="text-right text-zinc-300 break-all">{config.roomName}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500">Status</span>
          <span className={connectionState === ConnectionState.Connected ? 'text-emerald-400' : 'text-zinc-400'}>
            {connectionState}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500">User</span>
          <span className="text-zinc-300">{config.participant.name}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-zinc-500">Identity</span>
          <span className="text-right text-xs text-zinc-300 break-all">{config.participant.identity}</span>
        </div>
        {config.agentName && (
          <div className="flex justify-between">
            <span className="text-zinc-500">Agent</span>
            <span className="text-zinc-300">{config.agentName}</span>
          </div>
        )}
        <div className="flex justify-between gap-3">
          <span className="text-zinc-500">Agent identity</span>
          <span className="text-right text-xs text-zinc-300 break-all">{agentIdentity || 'Waiting'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500">Agent state</span>
          <span className="text-cyan-400">{debug.agentState || agentState}</span>
        </div>
      </section>

      <section className="border-t border-zinc-800 pt-4">
        <DebugPanel debug={debug} />
      </section>

      <section className="border-t border-zinc-800 pt-4">
        <MemoryPanel />
      </section>
    </div>
  );
}

export default function Playground(props: PlaygroundProps) {
  const [liveKitError, setLiveKitError] = useState<string | null>(null);
  const [hasLiveKitConnected, setHasLiveKitConnected] = useState(false);

  const handleConnected = useCallback(() => {
    console.info('LiveKit connected');
    setHasLiveKitConnected(true);
    setLiveKitError(null);
    props.onConnected();
  }, [props.onConnected]);

  const handleDisconnected = useCallback((reason?: DisconnectReason) => {
    console.warn('LiveKit disconnected', reason);
    if (hasLiveKitConnected || reason !== undefined) {
      setLiveKitError(reason ? `Disconnected from room: ${DisconnectReason[reason] ?? reason}` : 'Disconnected from room');
    }
  }, [hasLiveKitConnected]);

  const handleError = useCallback((error: Error) => {
    console.error('LiveKit error', error);
    setLiveKitError(error.message || String(error));
  }, []);

  const handleMediaDeviceFailure = useCallback((failure?: MediaDeviceFailure, kind?: MediaDeviceKind) => {
    console.error('LiveKit media device failure', failure, kind);
    const kindLabel = kind ? `${kind} ` : '';
    setLiveKitError(`Media device failure: ${kindLabel}${failure ?? 'unknown error'}`);
  }, []);

  return (
    <LiveKitRoom
      className="h-full overflow-hidden"
      serverUrl={props.config.serverUrl}
      token={props.config.token}
      connect={true}
      audio={true}
      video={false}
      onConnected={handleConnected}
      onDisconnected={handleDisconnected}
      onError={handleError}
      onMediaDeviceFailure={handleMediaDeviceFailure}
    >
      <PlaygroundContent
        {...props}
        onConnected={handleConnected}
      />
      {liveKitError && (
        <div className="fixed bottom-4 left-4 right-4 z-50 rounded border border-red-900 bg-red-950/90 px-4 py-3 text-sm text-red-200 shadow-xl">
          LiveKit: {liveKitError}
        </div>
      )}
    </LiveKitRoom>
  );
}
