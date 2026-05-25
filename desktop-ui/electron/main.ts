import { app, BrowserWindow, ipcMain, screen, session } from 'electron';
import {
  AccessToken,
  AgentDispatchClient,
} from 'livekit-server-sdk';
import path from 'path';
import fs from 'fs';
import net from 'net';

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
let activeRoomName: string | null = null;
const DEFAULT_AGENT_NAME = 'friday';

if (process.env.FRIDAY_CHROMIUM_LOGS !== 'verbose') {
  app.commandLine.appendSwitch('disable-logging');
  app.commandLine.appendSwitch('log-level', '3');
}

if (isDev && process.env.FRIDAY_REMOTE_DEBUG_PORT) {
  app.commandLine.appendSwitch('remote-debugging-port', process.env.FRIDAY_REMOTE_DEBUG_PORT);
}

function debugLog(message: string, data?: Record<string, unknown>) {
  if (process.env.FRIDAY_DEBUG_LOGS === '1' || envConfig.FRIDAY_DEBUG_LOGS === '1') {
    console.log(message, data ?? '');
  }
}

function parseEnvValue(rawValue: string): string {
  const value = rawValue.trim();
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function loadEnv(): Record<string, string> {
  const env: Record<string, string> = {};

  const roots = Array.from(
    new Set([
      process.cwd(),
      app.getAppPath(),
      path.resolve(process.cwd(), '..'),
      path.resolve(app.getAppPath(), '..'),
      process.resourcesPath,
    ].filter(Boolean)),
  );

  const envFiles = roots.flatMap((root) => [
    path.join(root, '.env.local'),
    path.join(root, '.env'),
  ]);

  for (const filePath of envFiles) {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      content.split('\n').forEach((line) => {
        const trimmedLine = line.trim();
        if (!trimmedLine || trimmedLine.startsWith('#')) {
          return;
        }

        const separatorIndex = trimmedLine.indexOf('=');
        if (separatorIndex <= 0) {
          return;
        }

        const trimmedKey = trimmedLine.slice(0, separatorIndex).trim();
        if (!env[trimmedKey]) {
          env[trimmedKey] = parseEnvValue(trimmedLine.slice(separatorIndex + 1));
        }
      });
    }
  }

  return env;
}

let mainWindow: BrowserWindow | null = null;
let envConfig: Record<string, string> = {};

interface MemoryItem {
  key: string;
  value: string;
  category?: string;
  updated_at?: string;
}

interface MemoryData {
  items: MemoryItem[];
}

function createWindow() {
  envConfig = loadEnv();
  const preloadPath = resolveBuiltFile('../preload/preload.js', '../preload/preload.mjs');
  const { workAreaSize } = screen.getPrimaryDisplay();
  const windowWidth = Math.min(1400, Math.max(1000, workAreaSize.width));
  const windowHeight = Math.min(900, Math.max(680, workAreaSize.height));
  debugLog('[friday] env loaded', {
    hasLiveKitUrl: Boolean(envConfig.LIVEKIT_URL),
    hasLiveKitApiKey: Boolean(envConfig.LIVEKIT_API_KEY),
    hasLiveKitApiSecret: Boolean(envConfig.LIVEKIT_API_SECRET),
    defaultRoom: envConfig.FRIDAY_DEFAULT_ROOM || '',
    agentName: envConfig.FRIDAY_AGENT_NAME || DEFAULT_AGENT_NAME,
  });

  mainWindow = new BrowserWindow({
    width: windowWidth,
    height: windowHeight,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#09090b',
    autoHideMenuBar: true,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    show: false,
  });
  mainWindow.setMenuBarVisibility(false);

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }
}

function resolveBuiltFile(...relativePaths: string[]): string {
  for (const relativePath of relativePaths) {
    const absolutePath = path.join(__dirname, relativePath);
    if (fs.existsSync(absolutePath)) {
      return absolutePath;
    }
  }
  return path.join(__dirname, relativePaths[0]);
}

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback, details) => {
    const mediaDetails = details as { mediaTypes?: Array<'audio' | 'video'> };
    const isMediaPermission =
      permission === 'media' ||
      mediaDetails.mediaTypes?.includes('audio') === true;

    callback(isMediaPermission);
  });

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (mainWindow) {
    mainWindow.removeAllListeners('close');
    mainWindow.close();
  }
});

function generateRoomName(): string {
  return `room-friday-${Math.random().toString(36).slice(2, 10)}`;
}

function getActiveRoomName(): string {
  if (!activeRoomName) {
    activeRoomName = envConfig.FRIDAY_DEFAULT_ROOM || generateRoomName();
  }
  return activeRoomName;
}

function getLiveKitMode(livekitUrl: string): 'local' | 'cloud' {
  try {
    const host = new URL(livekitUrl).hostname.toLowerCase();
    return host === 'localhost' || host === '127.0.0.1' || host === '::1' ? 'local' : 'cloud';
  } catch {
    return 'cloud';
  }
}

function getLiveKitServiceUrl(livekitUrl: string): string {
  const parsedUrl = new URL(livekitUrl);
  if (parsedUrl.protocol === 'ws:') {
    parsedUrl.protocol = 'http:';
  } else if (parsedUrl.protocol === 'wss:') {
    parsedUrl.protocol = 'https:';
  }

  parsedUrl.pathname = parsedUrl.pathname.replace(/\/+$/, '');
  return parsedUrl.toString().replace(/\/$/, '');
}

function checkTcpPort(host: string, port: number, timeoutMs = 1500): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    let settled = false;

    const finish = (result: boolean) => {
      if (settled) {
        return;
      }
      settled = true;
      socket.destroy();
      resolve(result);
    };

    socket.setTimeout(timeoutMs);
    socket.once('connect', () => finish(true));
    socket.once('timeout', () => finish(false));
    socket.once('error', () => finish(false));
  });
}

function getMemoryPath(): string {
  if (envConfig.FRIDAY_MEMORY_PATH) {
    return path.resolve(envConfig.FRIDAY_MEMORY_PATH);
  }

  const localAppData = process.env.LOCALAPPDATA || app.getPath('userData');
  return path.join(localAppData, 'FridayAgent', 'memory.json');
}

function isSensitiveMemory(text: string): boolean {
  const lowered = text.toLowerCase();
  return ['password', 'secret', 'token', 'api key', 'apikey', 'credential', 'private key']
    .some((term) => lowered.includes(term));
}

function readMemory(): MemoryData {
  const memoryPath = getMemoryPath();
  if (!fs.existsSync(memoryPath)) {
    return { items: [] };
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(memoryPath, 'utf-8')) as Partial<MemoryData>;
    return Array.isArray(parsed.items) ? { items: parsed.items } : { items: [] };
  } catch {
    return { items: [] };
  }
}

function writeMemory(data: MemoryData) {
  const memoryPath = getMemoryPath();
  fs.mkdirSync(path.dirname(memoryPath), { recursive: true });
  fs.writeFileSync(memoryPath, JSON.stringify(data, null, 2), 'utf-8');
}

async function assertLocalLiveKitReachable(livekitUrl: string) {
  if (getLiveKitMode(livekitUrl) !== 'local') {
    return;
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(livekitUrl);
  } catch {
    throw new Error(`Invalid LIVEKIT_URL: ${livekitUrl}`);
  }

  const port = parsedUrl.port ? Number(parsedUrl.port) : parsedUrl.protocol === 'wss:' ? 443 : 80;
  const reachable = await checkTcpPort(parsedUrl.hostname, port);
  if (!reachable) {
    throw new Error(
      `Local LiveKit is not reachable at ${livekitUrl}. Start it with scripts\\start-livekit-local.ps1, then restart the desktop UI.`,
    );
  }
}

async function dispatchAgentToRoom(params: {
  roomName: string;
  agentName: string;
  metadata?: string;
}) {
  const apiKey = envConfig.LIVEKIT_API_KEY;
  const apiSecret = envConfig.LIVEKIT_API_SECRET;
  const livekitUrl = envConfig.LIVEKIT_URL;

  if (!apiKey || !apiSecret || !livekitUrl) {
    throw new Error('LiveKit credentials not configured. Please set LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL in .env.local');
  }

  await assertLocalLiveKitReachable(livekitUrl);

  const client = new AgentDispatchClient(getLiveKitServiceUrl(livekitUrl), apiKey, apiSecret);
  const existingDispatches = await client.listDispatch(params.roomName).catch((error: unknown) => {
    debugLog('[friday] unable to list agent dispatches before create', {
      roomName: params.roomName,
      error: error instanceof Error ? error.message : String(error),
    });
    return [];
  });
  const matchingDispatches = existingDispatches.filter(
    (dispatch) => dispatch.agentName === params.agentName,
  );
  const existing = matchingDispatches.find((dispatch) => (dispatch.state?.jobs?.length ?? 0) > 0);

  if (existing) {
    debugLog('[friday] reusing existing agent dispatch', {
      roomName: params.roomName,
      agentName: params.agentName,
      dispatchId: existing.id,
    });
    return {
      dispatchId: existing.id,
      agentName: existing.agentName,
      roomName: existing.room,
      reused: true,
    };
  }

  for (const dispatch of matchingDispatches) {
    debugLog('[friday] deleting stale agent dispatch before create', {
      roomName: params.roomName,
      agentName: params.agentName,
      dispatchId: dispatch.id,
      jobs: dispatch.state?.jobs?.length ?? 0,
    });
    await client.deleteDispatch(dispatch.id, params.roomName).catch((error: unknown) => {
      debugLog('[friday] failed to delete stale dispatch', {
        roomName: params.roomName,
        dispatchId: dispatch.id,
        error: error instanceof Error ? error.message : String(error),
      });
    });
  }

  debugLog('[friday] creating explicit agent dispatch', {
    roomName: params.roomName,
    agentName: params.agentName,
  });

  const dispatch = await client.createDispatch(params.roomName, params.agentName, {
    metadata: params.metadata,
  });

  return {
    dispatchId: dispatch.id,
    agentName: dispatch.agentName,
    roomName: dispatch.room,
    reused: false,
  };
}

ipcMain.handle('friday:createToken', async (_event, params: {
  roomName: string;
  participantName: string;
  participantIdentity: string;
  participantMetadata?: string;
  participantAttributes?: Record<string, string>;
  agentName?: string;
  agentMetadata?: string;
}) => {
  const apiKey = envConfig.LIVEKIT_API_KEY;
  const apiSecret = envConfig.LIVEKIT_API_SECRET;
  const livekitUrl = envConfig.LIVEKIT_URL;

  if (!apiKey || !apiSecret || !livekitUrl) {
    throw new Error('LiveKit credentials not configured. Please set LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL in .env.local');
  }

  await assertLocalLiveKitReachable(livekitUrl);

  debugLog('[friday] creating participant token', {
    roomName: params.roomName,
    participantIdentity: params.participantIdentity,
    participantName: params.participantName,
    hasAgentName: Boolean(params.agentName),
  });

  const token = new AccessToken(apiKey, apiSecret, {
    identity: params.participantIdentity,
    name: params.participantName,
    metadata: params.participantMetadata,
    attributes: params.participantAttributes,
    ttl: '2h',
  });

  token.addGrant({
    roomJoin: true,
    room: params.roomName,
    canUpdateOwnMetadata: true,
  });

  const jwt = await token.toJwt();

  return {
    serverUrl: livekitUrl,
    participantToken: jwt,
  };
});

ipcMain.handle('friday:dispatchAgent', async (_event, params: {
  roomName: string;
  agentName: string;
  metadata?: string;
}) => {
  if (!params.roomName || !params.agentName) {
    throw new Error('Cannot dispatch agent without roomName and agentName');
  }

  return dispatchAgentToRoom(params);
});

ipcMain.handle('friday:getEnv', async () => {
  const livekitUrl = envConfig.LIVEKIT_URL || '';

  return {
    livekitUrl,
    livekitMode: livekitUrl ? getLiveKitMode(livekitUrl) : 'cloud',
    defaultRoom: envConfig.FRIDAY_DEFAULT_ROOM || '',
    roomName: getActiveRoomName(),
    agentName: envConfig.FRIDAY_AGENT_NAME || DEFAULT_AGENT_NAME,
    participantName: envConfig.FRIDAY_PARTICIPANT_NAME || 'Friday Desktop',
  };
});

ipcMain.handle('friday:getOrCreateRoom', async () => {
  const livekitUrl = envConfig.LIVEKIT_URL;

  if (!livekitUrl) {
    throw new Error('LiveKit credentials not configured');
  }

  await assertLocalLiveKitReachable(livekitUrl);

  return {
    roomName: getActiveRoomName(),
    serverUrl: livekitUrl,
    isNew: true,
  };
});

ipcMain.handle('friday:getMemory', async () => {
  return {
    path: getMemoryPath(),
    items: readMemory().items,
  };
});

ipcMain.handle('friday:saveMemoryItem', async (_event, item: MemoryItem) => {
  const key = item.key?.trim();
  const value = item.value?.trim();
  const category = item.category?.trim() || 'general';

  if (!key || !value) {
    throw new Error('Memory key and value are required');
  }

  if (isSensitiveMemory(key) || isSensitiveMemory(value)) {
    throw new Error('Friday memory will not store secrets, tokens, passwords, or credentials');
  }

  const data = readMemory();
  const now = new Date().toISOString();
  const existing = data.items.find((entry) => entry.key.toLowerCase() === key.toLowerCase());
  if (existing) {
    existing.value = value;
    existing.category = category;
    existing.updated_at = now;
  } else {
    data.items.push({ key, value, category, updated_at: now });
  }
  writeMemory(data);

  return {
    path: getMemoryPath(),
    items: data.items,
  };
});

ipcMain.handle('friday:forgetMemoryItem', async (_event, key: string) => {
  const data = readMemory();
  const normalizedKey = key.trim().toLowerCase();
  data.items = data.items.filter((entry) => entry.key.toLowerCase() !== normalizedKey);
  writeMemory(data);

  return {
    path: getMemoryPath(),
    items: data.items,
  };
});
