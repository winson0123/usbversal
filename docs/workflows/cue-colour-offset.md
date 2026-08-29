# Hot cue colour — PCO2 offset 28 (TASK-253)

**Found:** 2026-08-29, WONSIN `ANLZ0000.EXT` (8 hot cues, 72-byte PCP2 bodies).

We read `body[-3:]` as RGB. Those three bytes are comment padding, always
`00 00 00`. Every transferred cue was black in Serato.

The RGB is at **offset 28**:

| Slot | Colour |
|------|--------|
| 0 | `#FF0017` |
| 1 | `#00C4FF` |
| 2 | `#33FF00` |
| 3 | `#4D00FF` |
| 4 | `#00FF30` |
| 5 | `#FF5E00` |
| 6 | `#0000FF` |
| 7 | `#FFE800` |

Decision: read offset 28 on a body of 31 bytes or more. Fall back to the
last three bytes only for shorter layouts (old tests / older ANLZ).
Do not map onto a Serato palette until a re-sync shows Serato still
drops these values.
