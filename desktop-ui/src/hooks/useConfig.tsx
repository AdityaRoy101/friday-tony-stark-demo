import { useState, useEffect, useCallback } from 'react';
import type { ConnectionConfig, ParticipantInfo } from '../lib/types';
import { generateRoomName } from '../lib/utils';

export interface UseConfigReturn {
  config: ConnectionConfig;
  updateConfig: (updates: Partial<ConnectionConfig>) => void;
  updateParticipant: (updates: Partial<ParticipantInfo>) => void;
  resetConfig: () => void;
  isConfigValid: () => boolean;
}

export function useConfig(): UseConfigReturn {
  const [config, setConfig] = useState<ConnectionConfig>(() => {
    const savedConfig = localStorage.getItem('friday-config');
    const defaults = {
      mode: 'manual' as const,
      roomName: generateRoomName(),
      participant: {
        identity: 'user-' + Math.random().toString(36).substring(2, 8),
        name: 'User',
        attributes: {},
      },
      agentName: '',
    };
    if (savedConfig) {
      try {
        return { ...defaults, ...JSON.parse(savedConfig) };
      } catch {
        return defaults;
      }
    }
    return defaults;
  });

  useEffect(() => {
    localStorage.setItem('friday-config', JSON.stringify(config));
  }, [config]);

  const updateConfig = useCallback((updates: Partial<ConnectionConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }));
  }, []);

  const updateParticipant = useCallback((updates: Partial<ParticipantInfo>) => {
    setConfig((prev) => ({
      ...prev,
      participant: { ...prev.participant, ...updates },
    }));
  }, []);

  const resetConfig = useCallback(() => {
    const newConfig = {
      mode: 'manual' as const,
      roomName: generateRoomName(),
      participant: {
        identity: 'user-' + Math.random().toString(36).substring(2, 8),
        name: 'User',
        attributes: {},
      },
      agentName: '',
    };
    setConfig(newConfig);
    localStorage.setItem('friday-config', JSON.stringify(newConfig));
  }, []);

  const isConfigValid = useCallback(() => {
    if (config.mode === 'manual') {
      return !!config.serverUrl && !!config.token && !!config.roomName && !!config.participant.identity;
    }
    return !!config.roomName && !!config.participant.identity;
  }, [config]);

  return { config, updateConfig, updateParticipant, resetConfig, isConfigValid };
}