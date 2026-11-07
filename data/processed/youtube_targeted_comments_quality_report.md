# YouTube targeted comments quality report

This report describes the combined comment file. It does not infer who the commenters are, whether they are first-time investors, or why anyone stopped a SIP.

Language detection has not been performed.

## Size

- Total rows before deduplication: 2692
- Unique comments after deduplication: 2692
- Duplicate comment IDs removed: 0
- Rows skipped because the comment id was missing: 0
- Unique videos in the master file: 76
- Unique channels in the master file: 55
- Empty comments: 1

The review sheet had 83 videos marked include. A video appears in this file only when at least one comment was saved. Videos with no saved comments are not counted above.

## Comments per batch

Counts below are rows read from each raw file before duplicate comment ids were removed.

| Batch | Comments read |
| ---: | ---: |
| 1 | 726 |
| 2 | 351 |
| 3 | 356 |
| 4 | 120 |
| 5 | 264 |
| 6 | 146 |
| 7 | 87 |
| 8 | 499 |
| 9 | 143 |

## Missing values by column

A value is missing when the cell is empty after reading. Comment text is not rewritten.

| Column | Empty cells |
| --- | ---: |
| `video_id` | 0 |
| `video_title` | 0 |
| `channel` | 0 |
| `video_url` | 0 |
| `comment_id` | 0 |
| `comment_text` | 1 |
| `comment_published_at` | 0 |
| `like_count` | 0 |
| `discovery_search_query` | 0 |
| `collection_batch` | 0 |

## Comments per video

| Video id | Comments |
| --- | ---: |
| `3NeW1eAqI3I` | 100 |
| `8Oi1wPVx2ag` | 100 |
| `Gr4UbZHAhIA` | 100 |
| `Mr5hz8IpNxI` | 100 |
| `XuuiXv8uoQU` | 100 |
| `fG8dVfU0P10` | 100 |
| `iJ1s0j0qJ0I` | 100 |
| `oIAQsjJEwj8` | 100 |
| `or3oYy6sXJ0` | 100 |
| `qxu7CBYR864` | 100 |
| `rVavcF0Otpg` | 100 |
| `xO415j3JB1Y` | 100 |
| `A_AsZyfUrvA` | 84 |
| `HVU_N2Odhbg` | 82 |
| `tiTNheLg50Q` | 80 |
| `QFVffpBj4NU` | 74 |
| `efTfvUwZMU8` | 71 |
| `S9QGWl1c_gE` | 59 |
| `SS0v6mXGmpY` | 58 |
| `H60n7TAI6GM` | 57 |
| `XdELUblWHqo` | 56 |
| `MV0fX5ECgX0` | 54 |
| `s5jwTIoRygY` | 47 |
| `7uZ7TctzPSk` | 41 |
| `e398lJTi0Bc` | 41 |
| `VQeYYJjRNq8` | 39 |
| `SDDZIE9rGEI` | 37 |
| `ILzijuV2WHI` | 35 |
| `gdxbs19Gt_E` | 35 |
| `8NUXjDS23QE` | 34 |
| `Bu1yhZPZg6o` | 30 |
| `S87-sUbcbiE` | 30 |
| `_jl8n4x4R4M` | 26 |
| `Tah29l2vKww` | 25 |
| `VYFkr_kuJQs` | 25 |
| `29C0zeH6ssg` | 23 |
| `LDLMvml2b7M` | 23 |
| `b_GDysqvedw` | 21 |
| `-7XCDpGkN-c` | 19 |
| `6qbp0vT4iI0` | 19 |
| `o1sqee-yRnw` | 17 |
| `z9y57D-MJ0w` | 17 |
| `KG7OtY-DtlM` | 16 |
| `fI8dpK1W2Wc` | 16 |
| `pZRqE687eG8` | 15 |
| `_2ipXexkOkA` | 14 |
| `PUmGpdugIT0` | 12 |
| `tEQVYxdf5JE` | 12 |
| `_78Df6KPzWc` | 11 |
| `l-5gx7CUCSk` | 11 |
| `F6VDOMvnveE` | 10 |
| `qjnDO4rzatk` | 10 |
| `-7cM07kM7j0` | 8 |
| `F3NX5yTEVBE` | 8 |
| `Qx1Uprf9c1A` | 8 |
| `ymEL-u3_Jjc` | 8 |
| `0ufmsxl-EtY` | 7 |
| `aE03ksx5RTA` | 7 |
| `1mqVEivmDXY` | 6 |
| `42E7faRE_20` | 6 |
| `kn_Kvy337C4` | 6 |
| `Sda4k5ZsLfc` | 5 |
| `pSzycPgHfu8` | 5 |
| `uj0Ghqa45QU` | 5 |
| `-iY0ZTHXNyw` | 4 |
| `YWPTOIovZqo` | 4 |
| `hYRbc_yM7S8` | 3 |
| `jYfQgurGEV8` | 3 |
| `Zg7iPczwKTc` | 2 |
| `j7nfH8TQdCA` | 2 |
| `pEw2f8RRHVg` | 2 |
| `xqbuZiJhG8g` | 2 |
| `zt2_FEYejxU` | 2 |
| `G2FFVHmq_Zc` | 1 |
| `SEIPbAJMgTk` | 1 |
| `YR2xZXfBdGY` | 1 |

## Duplicate comment IDs

No duplicate comment ids were found.

## Exact duplicate comment text

40 non-empty comment strings occur more than once (111 extra rows). The comment ids are different, so both rows are kept. Blank comments are not included in this list.

- 21 copies: Sip
- 9 copies: ❤
- 8 copies: SIP
- 8 copies: Thanks
- 6 copies: Bitcoin
- 5 copies: Direct
- 5 copies: Good
- 5 copies: No
- 5 copies: Thanks bro
- 5 copies: ❤❤❤
- 5 copies: 👍
- 4 copies: Regular
- 4 copies: Thank you sir
- 4 copies: ❤❤
- 3 copies: Excellent
- 25 further duplicate strings are not listed.

## File problems

All nine batch files were read and had the expected columns.

## Other notes

- Deduplication keeps the first row for a comment id. Batch 1 is read before batch 2, and so on.
- Like counts and dates are copied as text. They are not checked against YouTube.
- The same comment text on two ids can be two people posting the same words, or one person posting twice. This report does not decide which.
