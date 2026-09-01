# ADR 0002: asyncio and a dedicated Rekordbox thread

**Status:** accepted
**Date:** 2026-05-22

## Context

Opening a Rekordbox export and writing analysis tags are slow I/O. The
TUI still has to paint progress and take keys. rbox / PyOneLibrary
dies if you hop threads mid-handle. I learned that on a real stick,
not in a mock.

## Decision

Textual already runs on asyncio, so the app loop stays there.

Rekordbox open and `sync_playlists` run on one dedicated executor
thread, not the default `asyncio.to_thread` pool.

Analysis tag writes use a small worker pool so crate work can continue
on the Rekordbox thread.

There is no job registry, event bus, or job file on disk.

## Consequences

One process, which PyInstaller likes. Library, Progress, and quit all
talk to Rekordbox on the same thread. Progress is a normal callback.

The sync/async boundary is easy to get wrong. Tests that open rbox
must stay on that thread.

The analysis pool is capped so a USB stick is not flooded.
