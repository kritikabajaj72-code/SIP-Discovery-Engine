# YouTube evidence audit

Keyword matches are leads for human review. They are not confirmed investor experiences.

A question about stopping a SIP is not evidence that the author stopped one. Advice such as "never stop your SIP" is not personal experience. A missed payment is not labelled as discontinuation unless the comment also says the writer stopped or discontinued the SIP. This screen does not decide that someone is a first-time investor, and it does not invent a reason that the words do not state.

- Comments screened: 2692
- Comments with at least one keyword lead: 76
- Comments with no keyword lead: 2616

Every lead has `manual_verification_required` set to `true`. `possible_evidence_category` is the keyword bucket, not a final label. `evidence_quote` is a slice of the original comment.

## Leads by possible category

| Possible category | Comments |
| --- | ---: |
| `first_person_actual_discontinuation` | 6 |
| `intention_to_stop` | 0 |
| `temporary_pause` | 1 |
| `sip_cancellation` | 5 |
| `missed_payment` | 46 |
| `financial_difficulty` | 1 |
| `general_educational_discussion` | 17 |

## How a comment is bucketed

- `first_person_actual_discontinuation`: the text matches a first-person "I stopped" or "I discontinued" SIP pattern.
- `intention_to_stop`: the text matches wanting or planning to stop, and it does not match the stop-already pattern.
- `temporary_pause`: the text matches a first-person pause.
- `sip_cancellation`: the text matches a first-person cancellation.
- `missed_payment`: the text matches a missed instalment, missed payment, or a failed debit, and it does not match a stronger pattern above.
- `financial_difficulty`: the text contains an explicit money-problem phrase, and it does not match a stronger pattern above.
- `general_educational_discussion`: the text is advice not to stop, or a question about stopping, pausing, or cancelling, and it does not also match a first-person "I stopped" or "I discontinued" pattern.

If a comment matches more than one keyword, `keyword_matches` lists each hit. The category is only the first bucket that the rules above allow. A second keyword is not a finding that one thing caused another.

## What this audit does not do

- It does not call an AI model.
- It does not treat the video title as proof about the commenter.
- It does not count a comment as a personal discontinuation because the video was found with a search about stopping.
- Comments with no keyword hit are left out of `youtube_evidence_audit.csv`. Absence from that file is not proof that the comment has no useful meaning.
