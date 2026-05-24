# Desktop UI Reference Notes

This folder is the implementation target for the local Electron playground UI.

## Official Reference

- Hosted UI: https://agents-playground.livekit.io
- Official source: https://github.com/livekit/agents-playground
- LiveKit docs: https://docs.livekit.io/agents/start/playground
- Agents UI docs: https://docs.livekit.io/reference/components/agents-ui

LiveKit docs describe the playground as a frontend for testing multimodal agents with audio, text, and video. The official source README says the open-source playground can be run locally with `pnpm install`, `.env.local`, and `pnpm run dev`.

## Official Source Files To Inspect First

Core app:

- `src/pages/index.tsx`
- `src/components/PlaygroundConnect.tsx`
- `src/components/playground/Playground.tsx`
- `src/components/playground/PlaygroundHeader.tsx`
- `src/components/playground/PlaygroundTile.tsx`
- `src/components/playground/SettingsDropdown.tsx`

Chat:

- `src/components/chat/ChatTile.tsx`
- `src/components/chat/ChatMessage.tsx`
- `src/components/chat/ChatMessageInput.tsx`

Settings/config:

- `src/components/config/AttributesInspector.tsx`
- `src/components/config/AudioInputTile.tsx`
- `src/components/config/ConfigurationPanelItem.tsx`
- `src/components/config/NameValueRow.tsx`

Debug:

- `src/components/debug/debug-panel.tsx`
- `src/components/debug/event-log.tsx`
- `src/components/debug/metrics-display.tsx`
- `src/components/debug/audio-waveform.tsx`

Hooks/lib:

- `src/hooks/useConfig.tsx`
- `src/hooks/useRemoteSession.ts`
- `src/hooks/useUplinkLatency.ts`
- `src/hooks/useTrackVolume.tsx`
- `src/lib/types.ts`
- `src/lib/util.ts`
- `src/styles/globals.css`

## Electron Porting Differences

The official playground is Next.js. The desktop app should not use Next.js.

Replace:

- `next/head` with normal document title/meta handling.
- `next/font/google` with CSS/font fallback or local Inter install.
- `next/navigation` router usage with `window.history` / `localStorage`.
- `/api/token` with Electron IPC token generation.
- browser-hosted env with main-process `.env.local` loading.

## Local Repo Commands

From the repo root:

```powershell
uv run friday
uv run friday_voice
```

From this folder after implementation:

```powershell
npm install
npm run dev
```

## Non-Negotiable Security Rule

`LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` belong only in Electron main process. The renderer must receive only generated participant tokens, never raw secrets.
