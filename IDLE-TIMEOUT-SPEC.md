# Idle Timeout for `motif live` — Implementation Spec

## Overview

Port the VS Code extension's idle timeout feature to the CLI dashboard. When no new JSONL activity is detected for N seconds (default 300), auto-end the session: print the session summary card, save session to `~/.motif/sessions/`, and reset metrics for a new session. The dashboard keeps running and watches for new activity.

## Files to Change

### 1. `motif/live/metrics.py` — Add activity tracking and reset

**Add `last_activity_timestamp` field** in `__init__()`:
```python
self.last_activity_timestamp: float = 0.0
```

**Set timestamp in `ingest()`** — after the message loop, only when at least one message was processed:
```python
had_activity = False
for msg in messages:
    if msg.type == "assistant":
        # ... existing logic ...
        had_activity = True
    elif msg.type == "user":
        # ... existing logic ...
        had_activity = True
if had_activity:
    self.last_activity_timestamp = time.time()
```

**Add `reset()` method** — clears all session state:
```python
def reset(self):
    """Reset all session state for a new session."""
    self._token_events.clear()
    self._prompt_times.clear()
    self._session_last_ai.clear()
    self._request_tokens.clear()
    self.session_tokens = 0
    self.session_prompts = 0
    self.peak_aipm = 0.0
    self.peak_aipm_time = 0.0
    self.peak_concurrency = 0
    self._concurrency_samples.clear()
    self.session_start = time.time()
    self.last_activity_timestamp = 0.0
```

### 2. `motif/live/runner.py` — Add idle check in main loop

**Modify `run_live()` signature** to accept `idle_timeout: int = 300`.

**Add idle check inside `while running` loop** (after `engine.ingest()`, before `time.sleep()`):
```python
if (idle_timeout > 0
    and engine.last_activity_timestamp > 0
    and engine.session_tokens > 0):
    idle_seconds = time.time() - engine.last_activity_timestamp
    if idle_seconds >= idle_timeout:
        final = engine.compute()
        live.update(render_summary(final))
        save_session(final)
        console.print(f"\n[dim]Session auto-saved after {idle_timeout}s idle. Watching for new activity...[/dim]")
        engine.reset()
```

**Print idle timeout setting on startup:**
```python
if idle_timeout > 0:
    console.print(f"[dim]Idle timeout: {idle_timeout}s[/dim]")
else:
    console.print(f"[dim]Idle timeout: disabled[/dim]")
```

### 3. `motif/cli.py` — Add CLI option

Add Click option to the `live` command:
```python
@click.option("--idle-timeout", default=300, type=int,
              help="Auto-end session after N seconds of inactivity (0 to disable)")
```

Pass through to `run_live(idle_timeout=idle_timeout)`.

## No New Files Needed

All changes fit into existing files. `save_session()` and `render_summary()` already exist and are reused directly.

## Edge Cases

| Case | Behavior |
|------|----------|
| Fresh dashboard, no activity yet | `last_activity_timestamp == 0` — idle check skipped |
| Session with 0 tokens | `session_tokens > 0` guard — not saved |
| Multiple timeouts in one run | After `reset()`, `last_activity_timestamp` goes to 0; re-arms only after new activity arrives and goes idle |
| `--idle-timeout 0` | Feature disabled entirely |
| `--history` mode | Initial load sets `last_activity_timestamp`; idle clock starts from that moment |

## Reference Implementation

- VS Code: `motif-vscode/src/extension.ts:startIdleCheckTimer()`
- VS Code engine: `motif-vscode/src/metrics/engine.ts` — `lastActivityTimestamp`, `ingest()`, `reset()`

## Testing

1. Unit test: create `MetricsEngine`, ingest messages, verify `last_activity_timestamp > 0`; call `reset()`, verify all fields zeroed
2. Integration: run `motif live --idle-timeout 10` and wait — verify summary prints and metrics reset
