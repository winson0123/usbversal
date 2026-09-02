# Volume parent crate

Every synced crate sits under a real thumbdrive-named parent so Serato
shows one folder wrapping the Rekordbox tree.

```text
/media/$USER/MY_USB  +  (parent)          ->  MY_USB.crate          (empty)
/media/$USER/MY_USB  +  Contents          ->  MY_USB%%Contents.crate
/media/$USER/MY_USB  +  Gigs / Played / … ->  MY_USB%%Gigs%%Played%%….crate
```

`MY_USB.crate` is written empty on every sync. Children keep the `%%`
path. `neworder.pref` lists `MY_USB` first, then every `%%` ancestor
(`MY_USB%%Gigs`, `MY_USB%%Gigs%%Played`) even when those folder nodes
have no `.crate` file, then the leaves. Serato will not show a nested
crate whose ancestors are missing from that list.

The label is the mount folder name (`MY_USB` on `/media/$USER/MY_USB` or
`/Volumes/MY_USB`). On Windows the filesystem volume label is read from
the drive letter; an unlabeled stick uses the letter (`E`). When nothing
can be resolved, the name falls back to `USB`.

A re-sync writes the new names. Older crates without the prefix stay on
the stick until removed by hand.
