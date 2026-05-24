# MiniMax 2.7 Prompt: Build Friday Desktop LiveKit Playground UI

You are working in this repository:

`C:\Users\aa986\OneDrive\Desktop\livekit_agent\friday-tony-stark-demo`

Build a production-quality desktop Electron app inside:

`C:\Users\aa986\OneDrive\Desktop\livekit_agent\friday-tony-stark-demo\desktop-ui`

The goal is to replace the need to open `https://agents-playground.livekit.io` in a browser. The desktop app must visually and functionally match the official LiveKit Agents Playground as closely as possible, but run locally as an Electron + React + TypeScript app.

## Source Of Truth

Use the official open-source playground as the implementation reference:

- Hosted UI: `https://agents-playground.livekit.io`
- Official repo: `https://github.com/livekit/agents-playground`
- Official docs: `https://docs.livekit.io/agents/start/playground`

Important: the official playground source is Apache-2.0 licensed. If you copy or adapt code from it, preserve license/notice requirements and add attribution in this desktop app.

Do not invent a different design. Port the LiveKit Agents Playground UI and interaction model into Electron.

## Current Backend To Support

This local repo already has a working LiveKit voice agent:

- MCP server command: `uv run friday`
- Voice agent command: `uv run friday_voice`
- Agent file: `agent_friday.py`
- The agent uses LiveKit Agents with Sarvam/OpenAI/etc.

The Electron app is only the local desktop client/playground UI. It should connect to the same LiveKit room/project that the agent uses.

## Required Tech Stack

Use:

- Electron
- React
- TypeScript
- Vite
- Tailwind CSS
- `@livekit/components-react`
- `@livekit/components-styles`
- `livekit-client`
- `livekit-server-sdk`
- `framer-motion`
- `qrcode.react`
- Radix UI only where the official playground uses it or where needed

Recommended structure:

```text
desktop-ui/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
  postcss.config.js
  electron/
    main.ts
    preload.ts
  src/
    main.tsx
    App.tsx
    styles/globals.css
    components/
    hooks/
    lib/
```

## Security Requirements

Never expose `LIVEKIT_API_KEY` or `LIVEKIT_API_SECRET` to the React renderer.

Electron main process may read secrets from `.env` / `.env.local` and generate tokens using `livekit-server-sdk`.

Renderer should call the main process through a typed preload bridge:

```ts
window.fridayLiveKit.createToken({
  roomName,
  participantName,
  participantIdentity,
  participantMetadata,
  participantAttributes,
  agentName,
  agentMetadata
})
```

Use:

- `contextIsolation: true`
- `nodeIntegration: false`
- `sandbox: false` only if required, otherwise keep sandbox-friendly defaults
- no direct secret access from renderer

## Environment Variables

Support local config from `desktop-ui/.env.local` first, and fall back to root `.env` if useful.

Required:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

Optional:

```env
FRIDAY_DEFAULT_ROOM=
FRIDAY_AGENT_NAME=
FRIDAY_PARTICIPANT_NAME=Friday Desktop
```

## Exact UI Requirements

Match the official Agents Playground UI:

1. Black full-window background with the subtle repeating square/grid pattern.
2. Centered connect screen when disconnected.
3. Connect card:
   - title: `Connect to playground`
   - subtitle explaining LiveKit Cloud/manual connection
   - tabs for `LiveKit Cloud` and `Manual` if cloud OAuth is implemented; otherwise show `Manual` plus a local token mode.
   - URL input
   - token text area for manual mode
   - Connect button
4. Connected screen:
   - header height about 56px
   - title `LiveKit Agents Playground` or configurable `Friday Playground`
   - status indicator
   - Connect/Disconnect button
   - settings dropdown/input toggles if ported
5. Main layout at desktop size:
   - left column: `Agent Video` tile and `Agent Audio` tile
   - middle column: `Chat` tile
   - right column: settings/config tile
   - optional debug panel at bottom when client events exist
6. Mobile/small width:
   - tabbed tile UX like official source
   - tabs: Video, Audio, Chat, Settings
7. Agent Audio tile:
   - use LiveKit `BarVisualizer`
   - state driven by `useAgent`
   - 5 bars, LiveKit theme color
8. Chat tile:
   - show session messages/transcripts
   - allow text input to send messages
   - preserve the official dark styling
9. Settings tile:
   - room name
   - connection status
   - agent name
   - agent identity
   - user name
   - user identity
   - participant attributes/metadata editor
   - camera/microphone/screen preview areas if enabled
   - color picker
   - QR code optional
10. Debug panel:
   - include event log, latency metrics, usage metrics, audio waveform/overlap diagnostics if practical
   - if full parity is too large, implement the visible shell and core event log first, but keep component boundaries ready.

Do not create a marketing landing page. The first screen must be the actual playground connection UI.

## Functional Requirements

The app must support two connection modes:

### Mode A: Local Token Generation

User enters or accepts:

- room name, default random `room-xxxxxxxx`
- participant name
- participant identity
- agent name optional
- participant metadata/attributes optional

Electron main process generates a LiveKit token using `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`.

Renderer connects using:

- server URL from env
- generated token

### Mode B: Manual URL + Token

User can paste:

- `wss://...livekit.cloud`
- participant token

Renderer connects directly with that literal token source.

## LiveKit Behavior

Use current LiveKit React APIs equivalent to the official playground:

- `SessionProvider`
- `useSession`
- `useAgent`
- `useSessionMessages`
- `RoomAudioRenderer`
- `StartAudio`
- `VideoTrack`
- `BarVisualizer`

The app must:

- request microphone permission cleanly in Electron
- allow camera enable/disable
- allow microphone enable/disable
- allow screen share if possible
- render agent audio and video tracks
- render local mic visualization/settings preview
- play agent audio through the desktop app
- support text chat to the agent
- show connection state changes
- disconnect cleanly and generate a fresh room name when needed

For Electron media permissions, implement main-process permission handlers for:

- microphone
- camera
- display capture / screen share if supported

## Important Electron Notes

In Electron, browser APIs behave slightly differently from Chrome. Verify:

- microphone permission prompt works
- `navigator.mediaDevices.getUserMedia({ audio: true })` works
- LiveKit room connection works
- `RoomAudioRenderer` actually plays remote audio
- app can reconnect after disconnect
- app closes cleanly without orphaned renderer errors

## Visual Quality Bar

The final UI must look like a real desktop app:

- no default browser form styling
- no oversized cards
- no nested cards except the official tile/card structure
- no explanatory feature text beyond what the official playground has
- no one-color purple/blue gradient redesign
- tight, dark, utilitarian LiveKit look
- responsive layout must not overlap or cut off text

Use the official Tailwind class approach from `livekit/agents-playground` as much as possible.

## Implementation Plan

1. Inspect the official `livekit/agents-playground` source.
2. Port the core React components into `desktop-ui/src/components`.
3. Replace Next.js-specific parts:
   - remove `next/head`
   - remove `next/font`
   - replace Next router/hash handling with browser history/localStorage
   - replace `/api/token` with Electron IPC token generation
   - replace Next env handling with Vite/Electron env handling
4. Implement Electron main/preload token bridge.
5. Implement local/manual connect screen.
6. Implement connected playground view.
7. Add app scripts.
8. Verify with a real LiveKit room and the existing `uv run friday_voice` agent.

## Required Scripts

Add scripts:

```json
{
  "dev": "electron-vite dev",
  "build": "electron-vite build",
  "typecheck": "tsc --noEmit",
  "lint": "eslint .",
  "preview": "electron-vite preview"
}
```

If using a different Electron/Vite setup, keep commands equivalent and document them.

## Acceptance Criteria

The work is not complete until all are true:

1. `cd desktop-ui && npm install` works.
2. `npm run typecheck` passes.
3. `npm run build` passes.
4. `npm run dev` launches a desktop Electron window.
5. The disconnected screen visually matches the hosted playground connect UI.
6. Local token generation connects to a LiveKit room.
7. Manual URL/token connection works.
8. With `uv run friday_voice` running, the desktop app can talk to the Friday agent.
9. Mic input reaches the agent.
10. Agent audio plays back.
11. Chat messages/transcripts are visible.
12. Disconnect/reconnect works without restarting the app.
13. Secrets are never visible in renderer source, devtools, or bundled frontend env.

## Deliverables

Create or update:

```text
desktop-ui/
  README.md
  package.json
  src/...
  electron/...
```

`desktop-ui/README.md` must include:

- setup commands
- required env vars
- how to run the MCP server
- how to run the LiveKit voice agent
- how to run the Electron UI
- troubleshooting for mic/audio permissions
- note that UI is adapted from Apache-2.0 `livekit/agents-playground`

## Do Not Do

- Do not modify the working Python voice agent unless absolutely necessary.
- Do not put LiveKit API secrets in React/Vite public env vars.
- Do not require opening `https://agents-playground.livekit.io`.
- Do not build a different UI.
- Do not remove manual URL/token mode.
- Do not skip typecheck/build verification.

Build this carefully and verify it end to end.
