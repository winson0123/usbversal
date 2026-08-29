# Volume parent crate

Every synced crate sits under a real thumbdrive-named parent so Serato
shows one folder wrapping the Rekordbox tree.

```text
/media/crow/WONSIN  +  (parent)          ->  WONSIN.crate          (empty)
/media/crow/WONSIN  +  Contents          ->  WONSIN%%Contents.crate
/media/crow/WONSIN  +  Gigs / Played / … ->  WONSIN%%Gigs%%Played%%….crate
```

`WONSIN.crate` is written empty on every sync. Children keep the `%%`
path. `neworder.pref` lists `WONSIN` first, then every `%%` ancestor
(`WONSIN%%Gigs`, `WONSIN%%Gigs%%Played`) even when those folder nodes
have no `.crate` file, then the leaves. Serato will not show a nested
crate whose ancestors are missing from that list.

The label is the mount folder name (`WONSIN` on `/media/$USER/WONSIN` or
`/Volumes/WONSIN`). A path with no folder name (a bare drive letter)
becomes `USB`.

A re-sync writes the new names. Older crates without the prefix stay on
the stick until removed by hand.
