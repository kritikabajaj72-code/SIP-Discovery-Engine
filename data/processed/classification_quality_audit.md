# Classification quality audit

This is an audit of the existing 100-record pilot in `classified_records_pilot.csv`. It is not a correction of those labels, and it is not a finding about the full dataset. No classification was changed.

A row is included only when `unsupported_inference` is true. The flag means the classifier or its validation rules recorded an unsupported conclusion. Many of those conclusions were already replaced with `unknown` or with a more general label before this file was saved. This audit reads that record. It does not decide that every flagged row still contains a wrong label.

## Coverage

- Pilot records read: 100
- `unsupported_inference` true: 45
- `unsupported_inference` false: 55
- Confirmed errors: 20
- Cases requiring human review: 25

Confirmed error means the stored reason names a conclusion, and the original text, read without translation, does not state that conclusion. Human review means the comment is not in English, the removed label may still be a fair reading, or the reason does not name the label that was rejected.

## Inference types

Each row has one primary type. A second type is counted only in the note below the table. No row was given a type unless the stored reason or a still-present label supported it.

| Inference type | Confirmed errors | Human review |
| --- | ---: | ---: |
| Invented personal investor history | 11 | 0 |
| Confusing general discussion with personal behaviour | 2 | 4 |
| Treating missed instalments as discontinuation | 0 | 0 |
| Inferring financial circumstances without evidence | 0 | 0 |
| Assigning root causes without supporting text | 1 | 0 |
| Other | 6 | 21 |

Rows whose primary type is something else, but which also record an unsupported root-cause category: 2. One of those is in human review, because the comment may still describe a personal SIP.

The human-review column is not a count of confirmed errors. 6 of those rows have a stored reason that describes the comment but does not name the label that was rejected.

### Invented personal investor history

These confirmed rows record that an active journey, a stopped journey, or `actively_continuing` was removed. The text does not say the writer is continuing or has stopped a SIP. Comments that do state a personal SIP history are in the human-review list instead of this group.

Example record ids: `00c521c4-dff3-4627-aa1a-240367c433a8`, `07e93014-5342-4346-9259-3403f726c457`, `0f2baa9e-29e6-4831-925b-ba322468b0cb`.

### Confusing general discussion with personal behaviour

These confirmed rows record that a discontinuation or intention label was removed, or a continuation label is still stored after that behaviour was removed. Advice, app complaints, and a non-SIP portfolio comment are not treated as the writer stopping a SIP.

Example record ids: `028f26a2-27a3-43d2-be20-4fad57162be0`, `local-08043d83111e20a9`.

### Treating missed instalments as discontinuation

Confirmed errors of this type: 0. No flagged row describes a missed instalment that was kept as discontinuation. Two rows still have behaviour `missed_installment` and continuation `missed_instalment`. Their flag comes from an active journey stage that was removed. Those missed-instalment labels were not reclassified.

### Inferring financial circumstances without evidence

Confirmed errors of this type: 0. Among the flagged rows, no saved root-cause detail states income, age, first-time status, or an unstated financial circumstance. Amounts and losses that appear in a comment are quotations from that comment, not inferred circumstances.

### Assigning root causes without supporting text

The confirmed rows of this type have a stored reason saying the root-cause category was not kept. The saved category is `unknown`. The rejected category name is not in the file, so this audit does not say which category was proposed. A saved detail that remains is a phrase present in the comment.

Example record ids: `local-07b7fe8b94f2a21b`.

### Other

Confirmed rows of this type either lost a behaviour label because the evidence quote was not in the text, or still have continuation `missed_instalment` after that behaviour was removed. The rejected behaviour name is not stored for the quote failures, so no more specific type is assigned.

## Confirmed errors still stored

These saved continuation labels still conflict with the behaviour left on the row. They were not corrected.

- `local-08043d83111e20a9` (YouTube): behaviour `unknown`, continuation `intention_to_discontinue`, evidence strength `none`.
  - Evidence quote: I don’t know if I should sell everything, sit and just wait
  - Note: The continuation label is still intention_to_discontinue. The behaviour is not considering_discontinuation, and the evidence strength is not strong. The comment is not used as proof that a SIP will be stopped.

- `07cc8fde-a222-4581-8ee3-11c6d48f5fc1` (Google Play): behaviour `unknown`, continuation `missed_instalment`, evidence strength `none`.
  - Evidence quote: kya matlab autopay ka jab khud hi pay krna pdta hai
  - Note: The continuation label is still missed_instalment after the missed-instalment behaviour was removed. The saved evidence strength is none. This is not counted as discontinuation. A personal continuation, active journey, or stopped journey label was removed because the text does not state it. The saved behaviour is the label left after that check.

## Confirmed errors already removed from the saved behaviour

18 confirmed rows name a label in `uncertainty_reason` that is no longer the saved behaviour. The reason is the evidence that the unsupported inference occurred. This audit does not put the removed label back and does not replace it with a new one.

## Cases requiring human review

25 flagged rows are not called errors here.

- `07c8b6c9-6e1d-4724-a2e3-14b87e6ce2c0` (Google Play): The stored reason describes the comment, but it does not name a label that was removed. The saved behaviour is left as stored. A person should decide whether any unsupported inference remains. Stored reason: Expressed as a feature question without explicit statement of ongoing personal SIP.
- `07e950cd-47c7-4584-95ff-8ee2f9f856df` (Google Play): The stored reason describes the comment, but it does not name a label that was removed. The saved behaviour is left as stored. A person should decide whether any unsupported inference remains. Stored reason: Feature request for portfolio grouping without stating personal SIP status.
- `08d53e3d-32d8-446f-b3cd-3aed1069ff19` (Google Play): The stored reason describes the comment, but it does not name a label that was removed. The saved behaviour is left as stored. A person should decide whether any unsupported inference remains. Stored reason: Feedback regarding app limitations without mentioning personal SIP status.
- `0d59686c-fe51-4e64-832b-ae37ac900651` (Google Play): The stored reason describes the comment, but it does not name a label that was removed. The saved behaviour is left as stored. A person should decide whether any unsupported inference remains. Stored reason: Review discusses mutual funds and app features generally without explicit personal SIP status.
- `local-02ef26799bf8cca3` (YouTube): The comment names two funds, says an SIP was done there, and asks whether it should be continued. The file says actively_continuing was removed. A person should decide whether that is a personal continuation statement. Stored reason: actively_continuing was removed because the writer does not say they are continuing a SIP. An active journey stage was removed because the writer does not say they are continuing.
- `local-03788dd0f5639633` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-06348d5abe992b11` (YouTube): The comment describes starting an SIP when the market falls and selling when it rises. The file says actively_continuing was removed. A person should decide what behaviour, if any, that describes. Stored reason: actively_continuing was removed because the writer does not say they are continuing a SIP. An active journey stage was removed because the writer does not say they are continuing.
- `local-0650b3b60dfebec1` (YouTube): The comment is Hindi in Latin script and mentions 2008 and a monthly amount. The file says actively_continuing was removed. A person should read it. This audit does not translate it into a behaviour. Stored reason: actively_continuing was removed because the writer does not say they are continuing a SIP. An active journey stage was removed because the writer does not say they are continuing.
- `local-06d145a896c1d1d0` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-06fe7e3a055a5c4b` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-073944ed898f86da` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-080daab4b7fa4331` (YouTube): The comment says “I started my SIP journey almost 3 years ago” and “No going back now.” The file says actively_continuing was removed. A person should decide whether those sentences state personal continuation. This audit does not confirm or reject that reading. Stored reason: actively_continuing was removed because the writer does not say they are continuing a SIP. An active journey stage was removed because the writer does not say they are continuing.
- `local-08b5c3b406fcdea7` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: Comment asking for part 2 of the SIP video. The behaviour label had no exact supporting excerpt, so it was not kept. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-0a3006c170d71f2c` (YouTube): The stored reason says explicitly_discontinued was removed. The comment is a short Hindi sentence that contains the English word SIP. A reader who knows the language should decide whether the writer says they stopped three SIPs. This audit does not treat the removal as a confirmed error and does not restore the label. Stored reason: explicitly_discontinued was removed because the text does not say the writer stopped their own SIP. A discontinuation conclusion was removed because the behaviour label does not support it. A stopped journey stage was removed because discontinuation is not established.
- `local-0bb23b591f92f794` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: Brief comment expressing gratitude for content about SIPs. The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-0db6416c156b6860` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-0e583abd75b3bcb5` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: Praising the method of doing SIP explained in the video. The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-0e59c1f6b10c3feb` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-10de65564252140e` (YouTube): The stored reason says the comment is not in English, so the behaviour was left unknown. This audit does not translate the comment or decide its behaviour. Stored reason: The comment is not in English, so a personal behaviour label was not accepted. The comment is mainly in a non-English language, so its personal meaning was left unknown.
- `local-11925dbc5b6f48be` (YouTube): The comment says an SIP was started and that a loss occurred. The file says an active journey stage was removed and a root-cause category was not kept. The saved detail “loss ho gya” appears in the comment. The rejected category name is not stored. A person should decide whether the sentence states a personal active SIP. Stored reason: An active journey stage was removed because the writer does not say they are continuing. The root-cause category was not kept because the stated cause did not support it.
- `local-11e8555d3c8f9943` (YouTube): The stored reason describes the comment, but it does not name a label that was removed. The saved behaviour is left as stored. A person should decide whether any unsupported inference remains. Stored reason: The user is asking how to understand their portfolio returns without mentioning SIPs explicitly.
- `local-19b4b15e04c4d306` (YouTube): The comment states an XIRR of 11% and asks whether to continue with mutual funds. The file says an active journey stage was removed. The return figure is in the comment. A person should decide whether the question states a personal active SIP. Stored reason: An active journey stage was removed because the writer does not say they are continuing.
- `local-1c7575bd0b3ff395` (YouTube): The stored reason describes the comment, but it does not name a label that was removed. The saved behaviour is left as stored. A person should decide whether any unsupported inference remains. Stored reason: Comment is a brief humorous remark about a portfolio.
- `local-1db6c358a0ccd51e` (YouTube): The comment says “I've been investing since 4 years” and gives invested and current amounts. The file says actively_continuing was removed. Those amounts are in the comment. A person should decide whether the sentence states continuation of a SIP rather than investing in general. Stored reason: Expresses disappointment with returns while stating ongoing investment, but does not state discontinuation. actively_continuing was removed because the writer does not say they are continuing a SIP. An active journey stage was removed because the writer does not say they are continuing.
- `local-1e45e5069d02d69f` (YouTube): The stored reason includes an English gloss of a Tamil or Manglish sentence and says actively_continuing was removed. This audit does not treat that gloss as confirmed evidence. Stored reason: Written in Manglish/Tamil script mixing English, stating investment was started based on a video. actively_continuing was removed because the writer does not say they are continuing a SIP. An active journey stage was removed because the writer does not say they are continuing.

## Limits

This audit covers the 100 classified pilot rows only. It does not call the classification model, does not change `classified_records_pilot.csv`, and does not claim that the pilot is representative or that any root cause caused a behaviour.
