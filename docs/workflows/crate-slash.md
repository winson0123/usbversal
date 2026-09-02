# Crate names that contain `/`

Windows and exFAT reject `/` in a filename, so `sanitize_crate_name`
cannot keep a real slash. Rekordbox playlists such as `Afro / Afro House`
must still show as a slash in Serato.

Use Serato's own escape. After renaming `Dance-pop / Dancehall` in
Serato on MY_USB, the file was:

```text
MY_USB%%Genres%%Dance-pop ␛␛2f Dancehall.crate
```

That is U+241B (SYMBOL FOR ESCAPE) twice, then ASCII `2f` (hex for `/`).
The crate body has no display name. The filename is the name. Do not
map `/` to `%%`. That would invent extra folder levels (`AC/DC` becomes
AC then DC). Other Windows-illegal characters (`<>:"\\|?*`) become `_`.

Earlier stand-ins (U+FF0F `／`, U+2215 `∕`) are deleted on the next
write so Serato does not show both spellings.
