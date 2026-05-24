# Local LiveKit Mode

Friday can run against LiveKit Cloud or a local LiveKit server. Local mode is the recommended development setup when the desktop UI and voice agent are on the same Windows laptop because it avoids a cloud round trip for signaling and media.

## Local Defaults

Use these values for local development:

```env
LIVEKIT_URL=ws://127.0.0.1:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

These are the standard development credentials used by `livekit-server --dev`.

## One-Time Setup

Install the LiveKit server binary into this repo:

```powershell
scripts\install-livekit-server-windows.ps1
```

This downloads the latest Windows AMD64 LiveKit server release from the official `livekit/livekit` GitHub repository into `tools\livekit-server\`. That folder is ignored by git.

If you already have `livekit-server` on your PATH or Docker installed, you can skip this install step.

## Switch This Repo To Local LiveKit

```powershell
scripts\use-livekit-local.ps1
```

The script updates only the `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` lines in root `.env`. It creates a timestamped `.env.livekit-cloud.<timestamp>.bak` backup first so you can return to LiveKit Cloud later.

## Start The Local Stack

Use four terminals:

```powershell
# Terminal 1: local LiveKit SFU
scripts\start-livekit-local.ps1
```

```powershell
# Terminal 2: MCP tool server
uv run friday
```

```powershell
# Terminal 3: LiveKit voice agent
uv run friday_voice
```

```powershell
# Terminal 4: Electron desktop playground
cd desktop-ui
npm run dev
```

## Health Check

```powershell
scripts\check-livekit-local.ps1
```

Expected result:

```text
OK: Local LiveKit is reachable at ws://127.0.0.1:7880
```

The desktop UI also checks this automatically. If local LiveKit is not running, it shows a clear startup error instead of silently disconnecting.

## Restore LiveKit Cloud

```powershell
scripts\restore-livekit-cloud-env.ps1
```

By default it restores the latest `.env.livekit-cloud.<timestamp>.bak` file. You can also pass a specific backup:

```powershell
scripts\restore-livekit-cloud-env.ps1 -BackupPath .\.env.livekit-cloud.20260524-153000.bak
```

## Notes

- Local mode does not reduce audio quality. It usually lowers latency for same-machine testing.
- Local mode is not a replacement for a properly deployed public LiveKit server if remote users need to connect.
- Keep `desktop-ui\.env.local` absent unless you intentionally want the desktop app to override root `.env`.
