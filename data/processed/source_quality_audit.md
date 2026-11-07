# Source quality and source-selection audit

This audit reads the two raw files only:

- `data/raw/youtube_sip_keyword_filtered.csv` (937 comments)
- `data/raw/sip_relevant_reviews.csv` (277 Google Play reviews)

No classification file was changed. The Gemini API was not called. Counts below are from these files. Video topics are read from titles only. This file does not say that a title topic caused any commenter to stop a SIP, and it does not treat the files as a representative sample of investors.

## Source-wise record counts

| Source | Rows | What the file contains |
| --- | ---: | --- |
| YouTube | 937 | Keyword-filtered comments. `keyword_match` is `True` on every row. The matched keyword itself is not stored. |
| Google Play | 277 | Reviews already flagged `sip_relevant` = `True` on every row. |

YouTube rows have a comment on one of 41 videos. Google Play rows are app reviews: Zerodha Coin 230, INDmoney 32, Groww 15.

## YouTube columns and metadata

Every YouTube row has these columns, and none of them is empty:

| Column | Filled rows | Distinct values |
| --- | ---: | ---: |
| `source` | 937 | 1 (`YouTube`) |
| `video_id` | 937 | 41 |
| `video_title` | 937 | 41 |
| `channel` | 937 | 35 |
| `video_url` | 937 | 41 |
| `comment` | 937 | 935 |
| `published_at` | 937 | 937 |
| `likes` | 937 | 123 (all numeric) |
| `keyword_match` | 937 | 1 (`True`) |

`video_id`, `video_title`, and `video_url` match one-to-one. The URL is a video link (`https://www.youtube.com/watch?v=` plus the video id). There is no comment id and no comment permalink. There is no video description, transcript, duration, or YouTube topic tag.

The title and channel are enough to name the original video. They are not enough to confirm what the video covers beyond the wording of the title. Some titles are stored with HTML entities (`&amp;`, `&#39;`, `&quot;`) rather than decoded characters. The channel value `Sanjay Kathuria` is stored with a trailing space.

Comment timestamps run from `2018-08-04` to `2026-11-06`. Counts by year: 2018: 2, 2019: 3, 2020: 2, 2021: 1, 2022: 9, 2023: 39, 2024: 116, 2025: 357, 2026: 408.

Two comment texts each appear on two different videos (4 rows). The other 933 comments are unique. Those repeated texts were not treated as proof of a bad row.

Of the 937 comments, 618 contain the word `SIP` or `SIPs`. The other 319 are in this keyword-filtered file but do not contain that word.

## Video-level coverage

- Unique videos: 41
- Unique channels: 35
- Comments per video: minimum 1, median 21, maximum 68
- The largest video contributes 68 comments (7.3% of 937)
- The 5 largest videos contribute 266 comments (28.4%)
- The 10 largest videos contribute 464 comments (49.5%)
- 12 videos have fewer than 10 comments (60 comments in total)
- 1 video has one comment
- 5 titles contain `#shorts` (145 comments)
- Channels with more than one video in this file: Sanjay Kathuria 3, and Finance Boosan, Pushkar Raj Thakur, Zero1 by Zerodha, and Rahul Jain - Hindi with 2 each

### The 30 videos with the most comments

The other 11 videos account for 51 comments and are not listed here. Topic labels use the title only, after decoding HTML entities. A label is not a description of the comments under that video.

| Comments | Topic from the title | Channel | Video title | Video id |
| ---: | --- | --- | --- | --- |
| 68 | Other: SIP mistakes | Rahul Jain - Hindi | 80% लोग SIP गलत तरीके से करते हैं! \| SIP का पूरा सच with Data Proof \| Grow Your Money - Rahul Jain | `oIhGHb30rWo` |
| 53 | SIP returns and performance | Mutual fund Guru | My mutual fund portfolio revealed total returns. Title also contains `#shorts` | `4zQKHOJagtI` |
| 49 | General mutual fund education | Sanjay Kathuria | How to Start SIP in Mutual Funds \| Beginners Guide | `ZXLATRO3Ifw` |
| 48 | SIP returns and performance | Akshat Shrivastava | Why SIP returns are Falling? (& will continue to fall) | `oIAQsjJEwj8` |
| 48 | General mutual fund education | Money Talks With Nikhil | How to Start SIP in 7 Steps \| Mutual Fund Investing Made Easy | `kjtTU_-MAAI` |
| 44 | Other: asks whether SIP is a scam | Udayan Adhye | SIP investing is a SCAM? | `jbGVmNdoJZU` |
| 40 | Other: mutual fund mistakes | Rahul Jain - Hindi | 10 BIG Mutual Fund Mistakes !! | `RpzKhdNvUFE` |
| 38 | SIP returns and performance | Sanjay Kathuria | Why SIPs Won't Make you Rich. Title also contains `#shorts` | `1VvTDIx4h8U` |
| 38 | Other: SIP mistakes | Mutual Funds with Groww | 5 SIP Mistakes Every Mutual Fund Investor Should Avoid | `8eI6zoGyRM4` |
| 38 | Other: mutual fund mistakes | Finance Boosan | 10 Mistakes that you must AVOID \| STOP Making These Mutual Fund Mistakes | `hJAzeosPf2A` |
| 36 | SIP returns and performance | Zero1 by Zerodha | Secret Trick that gives better returns than SIP | `wi8AGE0d63s` |
| 33 | Other: compares a ₹2,000 SIP with a ₹10,000 SIP. Title contains `#shorts` | warikoo | 2K ki SIP - 10K ki SIP se ZYADA - KAISE? | `iQLLna9o_EY` |
| 31 | General mutual fund education | Boss Wallah (Tamil) | How to Invest in SIP? \| SIP Fund Investment Guide in Tamil | `FFgwSwzSiyw` |
| 29 | SIP discontinuation or stopping investments. The title also says Nifty returns were negative | Sanjay Kathuria | Why Nifty Gave Negative Returns in Last 5 Years? \| Should you Stop SIPs Now? | `Mr5hz8IpNxI` |
| 28 | General mutual fund education | Finance Boosan | How to Start SIP & How SIP works? | `C2p7Bf1vNeA` |
| 28 | General mutual fund education | BBC News Hindi | SIP यानी Systematic Investment Plan में आप कैसे Invest कर सकती हैं, इसमें कितना फ़ायदा? | `_k1cz7sSuc4` |
| 24 | SIP discontinuation or stopping investments | NDTV Profit | "Stop Your SIPs", Shankar Sharma Sounds The Alarm For Retail Investors | `3NeW1eAqI3I` |
| 24 | Other: "dark truth" of SIP | Pushkar Raj Thakur: Stock Market Educator | The Dark Truth of SIP Investments | `Hk-_40wiLqY` |
| 24 | General mutual fund education | Pushkar Raj Thakur: Stock Market Educator | How to do SIP? Invest Money in Mutual Funds & ETF \| Step by Step Demo | `rAqzpRZa78E` |
| 22 | Other: mutual fund mistakes | Pranay Kapoor | Mutual Fund Mistakes Over 11 Years | `INviXxU36TM` |
| 21 | SIP discontinuation or stopping investments. The title also says two years of no returns | The Money Podcast with Neeraj & Vrinda | 2 Years of No Returns! Should You Stop Your SIP? | `QFVffpBj4NU` |
| 16 | SIP discontinuation or stopping investments | Abhishek Kar | Stop your SIPs right now says Shankar Sharma | `HVU_N2Odhbg` |
| 16 | SIP discontinuation or stopping investments | Value Research | Should You Stop Your SIP Now? | `8NUXjDS23QE` |
| 16 | General mutual fund education. Title contains `#shorts` | Kowshik Maridi | Mutual Funds లో Invest చేసి చూపిస్తా రండి! - Live Demo! | `5VLIqIOmOQI` |
| 14 | Other: asks whether SIP is the right choice | News Pinch | SIP वाकई सही है? | `hpQyHm6h6ZA` |
| 14 | Other: mutual fund mistakes. The title also says how to invest safely | Mr. GK | Mutual Fund Mistakes … How to Invest in Mutual Fund Safely? | `TRNTO9DBZVo` |
| 13 | Other: mutual fund myths | Zero1 by Zerodha | 3 Mutual Fund Myths You Need to Stop Believing | `mhuBS3CAiiQ` |
| 12 | General mutual fund education | DAY TRADER తెలుగు | How To Start SIP in Mutual Funds | `Gd8LXUn9E6U` |
| 12 | General mutual fund education | Dhruv Rathee | Mutual Funds Explained by Dhruv Rathee (Hindi) | `8A3s9WP_7l4` |
| 9 | SIP discontinuation or stopping investments | FinnovationZ by Prasad | Should You Stop Your SIP Now ?? Indian Market Update !! | `or3oYy6sXJ0` |

The video URL for each row is `https://www.youtube.com/watch?v=` followed by the video id.

### What the titles are primarily about

Each of the 41 videos is counted once. The first matching title rule wins. "STOP" in "stop making these mistakes" or "stop believing" is not counted as SIP discontinuation.

| Title topic | Videos | Comments under those videos |
| --- | ---: | ---: |
| SIP discontinuation or stopping investments | 8 | 124 |
| SIP pausing or missed instalments | 0 | 0 |
| SIP returns and performance | 5 | 180 |
| General mutual fund education | 10 | 257 |
| SIP selection and recommendations | 3 | 13 |
| App-specific issues | 0 | 0 |
| Other | 15 | 363 |

The 8 discontinuation titles ask whether to stop, quote someone telling viewers to stop, or say that SIP investors are pulling out. Three of those eight titles also mention returns or a falling market. They are counted only in the discontinuation row. No title uses pause, missed, instalment, or skip.

The returns row is five titles about portfolio returns, falling SIP returns, SIPs not making someone rich, a "better returns than SIP" claim, and a mid-cap fund profit short. The "Profit Plus" title asking how large an SIP must be to reach ₹1 crore is not in this row. "Profit" there is part of the channel name, not a performance claim.

The education row is how-to-start, how SIP works, a Tamil SIP guide, a live demo, a BBC explainer, and general "what are mutual funds" or beginner guides whose titles are instructional. "How To Invest For Beginners 2026" does not say SIP or mutual fund, so it is left in Other.

The selection row is three titles: how to choose a mutual fund (9 comments), best SIP plans for 2026 (2), and top-rated funds for a ₹500 SIP (2).

No video title is about an app fault. The channels Mutual Funds with Groww and Zero1 by Zerodha are brand channels. Their titles in this file are about SIP mistakes, myths, or returns, not about the apps.

The 15 Other videos are mostly mistakes, myths, a scam question, or a "dark truth" framing (9 videos, 301 comments). Three titles are about how large an SIP should be (40 comments). One title asks whether to continue when markets fall (3 comments). One is the beginner-investing title with no SIP word (5 comments). One asks whether SIP is really right (14 comments).

Comment text is thinner than the titles on personal stopping. Across 937 comments, these case-insensitive phrases occur:

- `discontinu`: 0
- `i stopped`: 0
- `cancelled my sip`: 0
- `stop my sip`: 1, and the sentence is "Why should I stop my sip"
- `stop your sip`: 1, and the sentence is "don't stop your sip just keep patience"
- `pause`: 4 comments. They ask whether pausing is all right, say someone can pause, ask whether to continue or pause, or tell fund houses to pause. None says "I paused my SIP"
- `missed`: 2 comments. One says "I did SIP and I missed it due to insufficient balance"

A comment under a "should you stop" video is not evidence that the writer stopped.

## Google Play

Columns in `sip_relevant_reviews.csv`:

`source`, `app`, `review_id`, `review_text`, `rating`, `date`, `app_version`, `helpful_votes`, `developer_reply`, `reply_date`, `sip_relevant`.

There is no store URL. `source` is `Google Play` on all 277 rows. `review_id` and `review_text` are present and unique on every row. `sip_relevant` is `True` on every row. `app_version` is empty on 31 rows. `developer_reply` and `reply_date` are empty on 25 rows. `helpful_votes` is `0` on 157 rows. Review timestamps run from `2024-10-12 04:33:50` to `2026-11-05 06:48:35`, and all 277 timestamps are distinct.

### Reviews by app

| App | Reviews |
| --- | ---: |
| Zerodha Coin | 230 |
| INDmoney | 32 |
| Groww | 15 |
| Total | 277 |

### Rating distribution

| Rating | Reviews |
| ---: | ---: |
| 1 | 103 |
| 2 | 37 |
| 3 | 26 |
| 4 | 27 |
| 5 | 84 |

By app:

| App | 1 | 2 | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zerodha Coin | 87 | 36 | 23 | 22 | 62 |
| INDmoney | 11 | 1 | 2 | 4 | 14 |
| Groww | 5 | 0 | 1 | 1 | 8 |

### SIP-related text versus other reviews

This file cannot answer how many Play reviews are general app reviews. Every row is already marked `sip_relevant` = `True`, and no companion file of reviews marked false is in `data/raw`.

Inside this filtered file, the review text itself is narrower than the flag:

- 96 reviews contain the word `SIP` or `SIPs`: Zerodha Coin 80, Groww 8, INDmoney 8
- 181 reviews do not contain that word
- 188 reviews contain `mutual fund`
- 19 reviews contain neither `SIP`/`SIPs` nor the phrase `mutual fund`. Several of those 19 still discuss XIRR, a mandate, an instalment, or MF charts

The flag and the word `SIP` are not the same thing.

### Payment, SIP management, cancellation, pausing, and discontinuation

These are exact text matches, not confirmed events.

**Payment failure, missed deduction, or a SIP payment that the reviewer says did not work:** 11 Zerodha Coin reviews. Eight name a SIP. One more says an instalment was due and AutoPay did not work, without the word SIP. The other two do not name a SIP: one reports a Coin UPI "payment gateway failure", and one says "My Payment fails every time" for mutual funds. The phrases are: "Unable to do SIP payment", "I missed my payment this month", "My SIPs keep getting missed", "no sip is deducted", "my SIP not deducted", "payment gateway failure", "Autopay has failed", "the AutoPay didn't work", "pending SIP payment", "SIP option doesn't work", and "My Payment fails every time".

Other payment wording is present and is not counted in those 11. Examples include a wish for a wallet instead of a mandate, a mandate set to ₹1 crore for a ₹1,000 SIP, a positive note that mandate creation is smooth, an INDmoney Insta Cash loan AutoPay, and an IPO UPI mandate. Those are not SIP payment failures.

**SIP management:** two reviews state a management problem in those words. One Zerodha Coin review says it is difficult to modify a SIP. One INDmoney review says the writer cannot find an option to adjust the SIP date and amount. A separate Zerodha Coin review praises step-up. Other reviews mention minimum SIP amounts or ask for goal features. Those were not counted as management failures.

**Cancellation:** one Zerodha Coin review. It criticises a cancel button on a pending order and the time taken to refund that order. It does not say the writer cancelled an SIP.

**Pausing:** one Zerodha Coin review, rated 5. It says "I hope pausing sips" are included, along with SWP and switching funds. It does not say the writer paused a SIP. No review contains `paused`.

**Discontinuation:** no review contains `discontinu`, `stopped my`, `stop my sip`, or `i stopped`. Seven reviews contain `redeem`. They discuss redeeming units, exit charges, a redemption being rejected, a feature while redeeming, or an error that blocks redemption. One Groww review says the writer opened a SIP account in 2019 and has been trying to redeem it for a year. That is a redemption stuck in the app, not a statement that the writer decided to stop investing. One Coin review says the writer might take the money out if an XIRR error is not fixed. That is a conditional remark, not a completed discontinuation.

## Data-quality limitations

- The YouTube file is already keyword-filtered, and the keyword that kept each comment is not stored. `keyword_match` cannot be used to separate discontinuation comments from education comments.
- Video topic can be guessed from the title only. Description and transcript are absent.
- Eight titles are discontinuation prompts from creators. Comments on those videos are not personal discontinuation records.
- No video title is about pausing or a missed instalment.
- Comment coverage is uneven: half of the comments sit on 10 of the 41 videos, and 145 comments sit on five Shorts.
- Titles contain HTML entities, and one channel value has a trailing space.
- The Play file has no URL, is already filtered to `sip_relevant` = `True`, and is mostly Zerodha Coin. Groww has 15 reviews and INDmoney has 32.
- A `sip_relevant` flag does not mean the review text is about SIP behaviour. Most Play reviews do not contain the word SIP.
- Play text about payment problems is real in this file, but it is app-operation text. It is not a set of investors explaining why they discontinued.

## Is this data suitable for SIP discontinuation research?

Not as the main source, and not as a reason to classify the remaining rows in the hope that discontinuation evidence will appear.

The YouTube extract is dominated by education, mistake, and returns titles. The eight stop-or-pullout titles are media prompts. Personal phrases such as "I stopped", "I discontinued", and "I cancelled my SIP" are absent from the comment text searched above. Pause and missed-instalment language is limited to a handful of comments.

The Play extract can show Zerodha Coin payment and deduction complaints, including missed payments and AutoPay failures. It does not contain a review that says the writer discontinued a SIP. The one pause mention is a feature wish. The one cancel mention is a pending-order button.

The files are usable for a narrower question: how this filtered YouTube set is tilted toward education and creator prompts, and how the filtered Play set records app payment friction, mostly for Zerodha Coin. They are not usable for a conclusion about why people stop SIPs.

## Recommendations before collecting or classifying more records

1. Keep a source log that stores the search keyword, the date collected, and whether the row was kept by a keyword filter. A single `True` flag cannot be audited later.
2. For YouTube, collect videos whose titles or descriptions are about pausing, missed instalments, cancellation, or a person stopping their own SIP. Do not add more general "how to start SIP", mistake, or returns videos and expect discontinuation evidence.
3. Store the video description, or a human topic label, with the video id. Do not assign the research topic from the title alone.
4. Store a comment id or comment URL so a finding can be opened on the comment rather than only on the video.
5. Decode HTML entities in titles before the next export, and trim channel names.
6. For Google Play, keep the reviews that the filter rejected, or document the filter in a separate note, so SIP-flagged reviews can be compared with other app reviews.
7. If the research needs more than one app, collect more Groww and INDmoney reviews on purpose. This file is 230 of 277 reviews from Zerodha Coin.
8. When new Play reviews are screened, keep payment-failure wording separate from mandate feature requests, and do not treat "redeem", "cancel order", or "I hope pausing is included" as discontinuation.
9. Do not use creator lines such as "Should you stop your SIP" or "don't stop your SIP" as evidence that an investor stopped.
