# Volume parent crate

Every synced crate is prefixed with the thumbdrive name so Serato groups
them under one parent.

```text
/media/crow/WONSIN  +  Contents          ->  WONSIN%%Contents.crate
/media/crow/WONSIN  +  Gigs / Played / … ->  WONSIN%%Gigs%%Played%%….crate
```

Serato invents the `WONSIN` folder from the `%%` path. No empty
`WONSIN.crate` file is written (same as TASK-245).

The label is the mount folder name (`WONSIN` on `/media/$USER/WONSIN` or
`/Volumes/WONSIN`). A path with no folder name (a bare drive letter)
becomes `USB`.

A re-sync writes the new names. Older crates without the prefix stay on
the stick until removed by hand.
