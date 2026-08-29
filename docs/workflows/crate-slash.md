# Crate names that contain `/` (TASK-254)

Windows and exFAT reject `/` in a filename, so `sanitize_crate_name` used
to turn it into `_`. Rekordbox playlists such as `Afro / Afro House` then
showed in Serato as `Afro _ Afro House`.

Decision: replace `/` with U+FF0F fullwidth solidus (`／`). It is legal
in a `.crate` filename and still reads as a slash. Do not map `/` to
`%%` — that would invent extra folder levels (`AC/DC` → AC → DC).
Other Windows-illegal characters (`<>:"\\|?*`) stay `_`.
