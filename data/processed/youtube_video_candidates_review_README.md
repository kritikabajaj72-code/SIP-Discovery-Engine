# How to review the YouTube candidate videos

The file to edit is `youtube_video_candidates_for_review.csv` in this folder. It was copied from `youtube_video_candidates.csv`. Do not edit the original candidate file.

Create the review sheet from the project folder:

```text
python -m src.review_youtube_candidates
```

That command does not call Gemini or any other API. It does not approve a video because the title contains SIP.

## What to do for each row

1. Open the CSV in a spreadsheet.
2. Read the title, channel, search query, and preliminary topic.
3. Open the video URL and watch enough of the video to judge it. The title alone is not evidence.
4. Leave a row blank if you have not reviewed it yet.
5. Fill only these three columns:

| Column | What to enter |
| --- | --- |
| `human_review_status` | `include`, `exclude`, or `unsure` |
| `human_review_reason` | One short sentence saying what you saw in the video |
| `evidence_type` | One value from the list below |

`preliminary_topic` was assigned from the title by a keyword rule. It is not a decision. Do not copy it into `evidence_type` unless the video itself supports that reading.

## Allowed evidence types

Use one of these exact values:

- `first_person_actual_discontinuation` — the speaker says they stopped or discontinued their own SIP
- `first_person_intention_to_stop` — the speaker says they are thinking of stopping, but has not said they stopped
- `first_person_financial_difficulty` — the speaker describes their own money problem affecting a SIP
- `first_person_missed_payment` — the speaker describes missing their own instalment or payment
- `first_person_pause_or_cancellation` — the speaker describes pausing or cancelling their own SIP
- `general_educational_discussion` — a guide, opinion, or advice that is not the speaker's own experience
- `other` — the video is about something else that is still clear
- `unknown` — you could not tell

A creator asking “Should you stop your SIP?” is not `first_person_actual_discontinuation`. Advice such as “don’t stop your SIP” is `general_educational_discussion` unless the speaker also describes their own action.

Save the spreadsheet as the same CSV when you are finished.
