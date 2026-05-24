# Friday Desktop UI

Desktop Electron app that provides a local playground UI for LiveKit Agents, powered by the Friday voice agent from this repository.

**UI adapted from Apache-2.0 licensed [livekit/agents-playground](https://github.com/livekit/agents-playground)**

## Quick Start

### 1. Install dependencies

```bash
cd desktop-ui
npm install
```

### 2. Configure environment

Prefer the root `.env` so the Python agent and desktop UI always use the same LiveKit server.

For local LiveKit, run from the repo root:

```powershell
scripts\use-livekit-local.ps1
scripts\start-livekit-local.ps1
```

If you intentionally want only the desktop UI to override root `.env`, create `desktop-ui/.env.local`:

```env
LIVEKIT_URL=ws://127.0.0.1:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

### 3. Run the Friday MCP server

From the repo root (terminal 1):

```bash
uv run friday
```

### 4. Run the Friday voice agent

From the repo root (terminal 2):

```bash
uv run friday_voice
```

### 5. Launch the desktop UI

From `desktop-ui` directory:

```bash
npm run dev
```

The Electron app will open. Use the connect screen to join a LiveKit room.

## Connection Modes

### Local Token Generation
Enter room name, participant name, and identity. The app generates a token via Electron main process (API secrets never reach renderer).

### Manual Mode
Paste your LiveKit server URL and participant token directly.

## Troubleshooting

### Microphone/Audio Permissions

The app requests microphone permission on first connect. If audio doesn't work:

1. Check system microphone permissions in Windows Settings
2. Ensure no other app is using the microphone
3. Try disconnecting and reconnecting

### Connection Issues

- Verify `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` are correct in `.env.local`
- Check that `uv run friday_voice` is running and connected to the same LiveKit project
- Ensure the room name matches between agent and desktop app
- In local mode, verify `scripts\check-livekit-local.ps1` passes before launching the desktop UI

### Build Errors

```bash
npm install
npm run typecheck  # Fix any TypeScript errors
npm run build      # Production build
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |
| `npm run typecheck` | TypeScript validation |
| `npm run lint` | ESLint check |

## Architecture

- **Electron main** (`electron/main.ts`): Handles API secrets and token generation via IPC
- **Preload** (`electron/preload.ts`): Exposes typed bridge `window.fridayLiveKit` to renderer
- **React app** (`src/`): Playground UI with SessionProvider for LiveKit connection

Security: API keys are only in Electron main process. Renderer receives pre-generated participant tokens.
