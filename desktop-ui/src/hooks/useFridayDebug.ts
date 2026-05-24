import { useEffect, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { useRoomContext } from '@livekit/components-react';
import type {
  EventLogEntry,
  FridayConversationItem,
  FridayDebugPacket,
  FridayDebugState,
  FridayLatencyMetrics,
} from '../lib/types';
import { generateId } from '../lib/utils';

const DEBUG_TOPIC = 'friday.debug';
const decoder = new TextDecoder();

function isTelemetryPacket(value: unknown): value is FridayDebugPacket {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as FridayDebugPacket).type === 'friday.telemetry' &&
    typeof (value as FridayDebugPacket).event === 'string'
  );
}

function mergeLatency(
  current: FridayLatencyMetrics,
  data: Record<string, unknown>,
): FridayLatencyMetrics {
  const maybeMetrics = data.metrics;
  if (typeof maybeMetrics !== 'object' || maybeMetrics === null) {
    return current;
  }

  return {
    ...current,
    ...(maybeMetrics as FridayLatencyMetrics),
  };
}

function eventTypeToLevel(event: string): string {
  if (event === 'error') {
    return 'error';
  }
  if (event.includes('interruption') || event.includes('guard')) {
    return 'warn';
  }
  return event;
}

function normalizeRole(role: unknown): FridayConversationItem['role'] {
  if (role === 'user') {
    return 'user';
  }
  if (role === 'assistant' || role === 'agent') {
    return 'agent';
  }
  return 'system';
}

export function useFridayDebug(): FridayDebugState {
  const room = useRoomContext();
  const [state, setState] = useState<FridayDebugState>({
    events: [],
    conversationItems: [],
    latency: {},
  });

  useEffect(() => {
    const handleData = (payload: Uint8Array, _participant?: unknown, _kind?: unknown, topic?: string) => {
      if (topic && topic !== DEBUG_TOPIC) {
        return;
      }

      let parsed: unknown;
      try {
        parsed = JSON.parse(decoder.decode(payload));
      } catch {
        return;
      }

      if (!isTelemetryPacket(parsed)) {
        return;
      }

      const event: EventLogEntry = {
        id: generateId(),
        timestamp: parsed.timestamp || Date.now(),
        type: eventTypeToLevel(parsed.event),
        data: {
          event: parsed.event,
          ...parsed.data,
        },
      };

      setState((current) => {
        const next: FridayDebugState = {
          ...current,
          events: [event, ...current.events].slice(0, 100),
          latency: mergeLatency(current.latency, parsed.data),
        };

        if (parsed.event === 'user_input_transcribed') {
          const transcript = String(parsed.data.transcript ?? '');
          if (parsed.data.isFinal) {
            next.finalTranscript = transcript;
            next.partialTranscript = undefined;
          } else {
            next.partialTranscript = transcript;
          }
        }

        if (parsed.event === 'agent_state_changed') {
          next.agentState = String(parsed.data.newState ?? '');
        }

        if (parsed.event === 'user_state_changed') {
          next.userState = String(parsed.data.newState ?? '');
        }

        if (parsed.event === 'error') {
          next.lastError = String(parsed.data.error ?? 'Unknown agent error');
        }

        if (parsed.event === 'conversation_item_added') {
          const text = String(parsed.data.text ?? '').trim();
          if (text) {
            const item: FridayConversationItem = {
              id: generateId(),
              role: normalizeRole(parsed.data.role),
              text,
              timestamp: parsed.timestamp || Date.now(),
              interrupted: Boolean(parsed.data.interrupted),
            };
            const key = `${item.role}:${item.text}`.toLowerCase();
            const exists = current.conversationItems.some(
              (existing) => `${existing.role}:${existing.text}`.toLowerCase() === key,
            );
            if (!exists) {
              next.conversationItems = [...current.conversationItems, item].slice(-80);
            }
          }
        }

        return next;
      });
    };

    room.on(RoomEvent.DataReceived, handleData);
    return () => {
      room.off(RoomEvent.DataReceived, handleData);
    };
  }, [room]);

  return state;
}
