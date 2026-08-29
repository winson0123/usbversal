# Crate names that contain `/`

Windows and exFAT reject `/` in a filename, so `sanitize_crate_name`
cannot keep a real slash. Rekordbox playlists such as `Afro / Afro House`
must still read as a slash in Serato.

Decision: replace `/` with U+2215 division slash (`∕`). It is legal in a
`.crate` filename and looks like `/`. Do not map `/` to `%%` — that would
invent extra folder levels (`AC/DC` → AC → DC). Other Windows-illegal
characters (`<>:"\\|?*`) stay `_`.

TASK-254 first used U+FF0F fullwidth solidus (`／`). Serato shows that as
a wide CJK slash. A re-sync deletes the old `／` file and drops that
spelling from `neworder.pref` so both names do not appear.
