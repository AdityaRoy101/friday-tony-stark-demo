import { contextBridge, ipcRenderer } from 'electron';

export interface CreateTokenParams {
  roomName: string;
  participantName: string;
  participantIdentity: string;
  participantMetadata?: string;
  participantAttributes?: Record<string, string>;
  agentName?: string;
  agentMetadata?: string;
}

export interface TokenResponse {
  serverUrl: string;
  participantToken: string;
}

export interface EnvConfig {
  livekitUrl: string;
  livekitMode: 'local' | 'cloud';
  defaultRoom: string;
  roomName: string;
  agentName: string;
  participantName: string;
}

export interface RoomInfo {
  roomName: string;
  serverUrl: string;
  isNew: boolean;
}

export interface MemoryItem {
  key: string;
  value: string;
  category?: string;
  updated_at?: string;
}

export interface MemoryResponse {
  path: string;
  items: MemoryItem[];
}

const api = {
  createToken: (params: CreateTokenParams): Promise<TokenResponse> => {
    return ipcRenderer.invoke('friday:createToken', params);
  },
  getEnv: (): Promise<EnvConfig> => {
    return ipcRenderer.invoke('friday:getEnv');
  },
  getOrCreateRoom: (): Promise<RoomInfo> => {
    return ipcRenderer.invoke('friday:getOrCreateRoom');
  },
  getMemory: (): Promise<MemoryResponse> => {
    return ipcRenderer.invoke('friday:getMemory');
  },
  saveMemoryItem: (item: MemoryItem): Promise<MemoryResponse> => {
    return ipcRenderer.invoke('friday:saveMemoryItem', item);
  },
  forgetMemoryItem: (key: string): Promise<MemoryResponse> => {
    return ipcRenderer.invoke('friday:forgetMemoryItem', key);
  },
};

contextBridge.exposeInMainWorld('fridayLiveKit', api);

declare global {
  interface Window {
    fridayLiveKit: typeof api;
  }
}
