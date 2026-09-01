# Volume flush after sync

`sync_playlists` calls `flush_mount` after every write, including when a
later step failed. There is no extra PyPI package for this.
Each OS already has a volume flush:

| OS | Call |
|----|------|
| Linux | `os.syncfs`, or libc `syncfs` when this Python has no `os.syncfs`, then `BLKFLSBUF` on the block device |
| macOS | `F_FULLFSYNC` on the mount directory |
| Windows | `FlushFileBuffers` on `\\.\E:` (`os.fsync` of that handle) |

File-level fsync does not flush FAT, directory, or boot-sector updates. A
whole-system `os.sync()` can return before vhci USB finishes. The Toilet
sync at 04:21:53 followed by a 04:22:45 disconnect lost async writes,
including boot-sector block 0. Windows Scan did not change the MP3 or crate
hashes.

The TUI does not unmount. After **Done**, unmount from Linux yourself
before Windows. Flush makes the data durable; it does not clear the exFAT
VolumeDirty flag. Linux sets that flag on the first write and only clears
it on unmount.
