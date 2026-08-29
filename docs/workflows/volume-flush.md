# Volume flush after sync

`sync_playlists` calls `flush_mount` after every real write (not a dry run),
including when a later step failed. That is `syncfs` on the mount directory
so FAT, directory, and boot-sector pages reach the device. File-level fsync
on crates and tags does not cover those.

The TUI does not unmount. After **Done**, unmount from Linux yourself before
Windows or Serato. Flush makes that unmount a clean handoff; it does not
clear the exFAT VolumeDirty flag on its own.

A clean volume that is only mounted in WSL and yanked does not trip Windows
Scan and Fix. The TUI is the first writer, and Linux sets dirty on the first
write.
