# AI-Powered SIP Discovery Engine

## Research findings and problem discovery — Groww

**Research stage:** Secondary research and initial problem discovery  
**Product selected:** Groww  
**Research scope:** Indian mutual fund and SIP investor experiences  
**Sources:** Google Play reviews and public YouTube comments

Counts below are taken from `google_play_reviews_master.csv`, `google_play_problem_categories.csv`, and `youtube_evidence_audit.md`. They are keyword leads and rating bands, not verified investor behaviour.

## 1. Research objective

Understand why first-time mutual fund investors may discontinue their Systematic Investment Plans (SIPs), identify recurring friction points across the investment journey, and develop an AI-powered discovery engine that converts fragmented public feedback into actionable product insights.

The research focuses on four potential dimensions:

1. Financial constraints and changing affordability.
2. Investment dissatisfaction and loss of confidence.
3. Operational friction, including failed payments and missed instalments.
4. Product usability, including SIP management and cancellation.

## 2. Research methodology

### Source A: Google Play reviews

Collected 1,500 newest English-language reviews from India listings. Reviews were not filtered by an SIP keyword at collection time.

| Application | Reviews |
| --- | ---: |
| Groww | 500 |
| Zerodha Coin | 500 |
| INDmoney | 500 |
| **Total** | **1,500** |

A later rule-based pass labelled SIP relevance and one primary problem category per review.

### Source B: YouTube comments

Collected 2,692 public top-level comments. The review sheet had 83 included videos. Only 76 of those videos have at least one saved comment. The comments come from 55 channels.

Comments were screened with keyword rules. A match is a lead for a person to read. It is not a confirmed personal experience.

### Methodological distinction

Google Play reviews are comments on a named app. YouTube comments are discussion under videos about SIPs and mutual funds. These two groups are not the same population, and neither group is a representative sample of first-time SIP investors.

## 3. Google Play findings

### 3.1 Rating distribution

Stars are the reviewer’s rating. They are not a measured quality score for the app.

| App | Negative (1–2) | Neutral (3) | Positive (4–5) |
| --- | ---: | ---: | ---: |
| Groww | 76 | 9 | 415 |
| Zerodha Coin | 243 | 44 | 213 |
| INDmoney | 150 | 25 | 325 |

No rating in this file was blank, so each app’s three bands sum to 500.

### 3.2 SIP relevance

Direct means the review text contains “SIP” or “systematic investment plan”. Indirect means another investment or problem keyword was present without that SIP phrase.

| App | Direct SIP mentions | Indirect relevance | Not relevant |
| --- | ---: | ---: | ---: |
| Groww | 3 | 24 | 473 |
| Zerodha Coin | 44 | 155 | 301 |
| INDmoney | 4 | 73 | 423 |

In this sample, Groww has very few reviews that mention a SIP by name. Zerodha Coin has more direct SIP wording than Groww or INDmoney. That difference describes this set of reviews. It does not by itself show that one app causes more SIP problems.

### 3.3 Potential problem categories

Each review has one primary category. Reviews with no problem keyword are `none`. The lists below are the categories with at least one review. They still need manual reading.

**Groww** (486 of 500 reviews had no problem keyword)

- 4 technical-issue leads
- 4 redemption or withdrawal leads
- 4 returns, losses, or dissatisfaction leads
- 2 KYC or onboarding leads
- 0 SIP payment-failure, missed-instalment, pause-or-cancellation, amount-or-date, or setup leads

**Zerodha Coin** (421 of 500 reviews had no problem keyword)

- 25 technical-issue leads
- 22 returns, losses, or dissatisfaction leads
- 14 redemption or withdrawal leads
- 5 SIP payment-failure leads
- 5 SIP amount or date leads
- 4 KYC or onboarding leads
- 3 SIP setup or registration leads
- 1 missed-instalment lead

**INDmoney** (444 of 500 reviews had no problem keyword)

- 31 technical-issue leads
- 16 returns, losses, or dissatisfaction leads
- 4 KYC or onboarding leads
- 4 redemption or withdrawal leads
- 1 SIP amount or date lead

A payment-failure phrase does not prove the writer discontinued a SIP. A cancellation or pause phrase does not prove that action was completed. A feature complaint does not prove the writer is a first-time investor. A larger count is not, by itself, a worse app. The three apps contributed the same number of reviews, but the share of SIP wording is not the same.

## 4. YouTube findings

The consolidated file has 2,692 comments, 76 videos, and 55 channels. One comment text is empty. No duplicate comment id was removed. Forty non-empty strings appear more than once under different comment ids.

Keyword screening marked 76 comments as leads:

| Possible evidence category | Comments |
| --- | ---: |
| Missed payment | 46 |
| General educational discussion | 17 |
| First-person stopped or discontinued wording | 6 |
| First-person cancellation wording | 5 |
| Temporary pause | 1 |
| Explicit financial difficulty | 1 |
| Intention to stop | 0 |

These are keyword matches, not verified personal experiences. A question about stopping a SIP was not counted as the author having stopped. Advice such as “never stop your SIP” was not counted as personal experience. A missed payment was not counted as discontinuation unless the comment also used a first-person stop or discontinue phrase.

The six stop-or-discontinue comments and the five cancellation comments are the clearest candidates for manual review. They are not yet a count of people who discontinued a SIP. The comments are also not labelled by app, so they cannot be assigned to Groww from the comment file alone.

## 5. Emerging problem hypotheses

These are questions for the next stage of research. None is an established cause of first-time investor discontinuation.

### Hypothesis 1: Payment and operational friction

Investors may miss SIP instalments because a deduction fails, a mandate is hard to manage, or the next step after a missed payment is unclear.

The Play sample’s payment-failure and missed-instalment leads are on Zerodha Coin (5 and 1), not on Groww (0 and 0). The YouTube screen has 46 missed-payment leads, and those comments are not tied to one app.

Possible product questions:

- Where do failed instalments get explained?
- What recurring payment wording appears after a person reads the original review or comment?
- What does the text say the person did next?

### Hypothesis 2: Financial affordability

Some investors may find a fixed monthly amount hard to keep when expenses or income change.

The YouTube screen has 1 comment with an explicit financial-difficulty phrase and 0 comments matched as intention to stop. That is not enough first-person evidence to treat affordability as a demonstrated cause.

Possible product questions:

- Where do people state that they cannot afford the SIP?
- Where do they ask to reduce the amount, rather than stop?
- What flexible options, if any, do they name?

### Hypothesis 3: Investment disappointment

Investors may lose confidence when returns are below what they expected or when markets fall.

Return, loss, or dissatisfaction is a primary category for 4 Groww reviews, 22 Zerodha Coin reviews, and 16 INDmoney reviews. YouTube titles in the earlier source audit were often about returns or “should you stop”, which is creator framing, not proof that the commenter stopped.

Possible product questions:

- Which comments state a personal loss of confidence?
- Which comments confuse a short-term fall with a reason to stop a long-term SIP?
- Which statements are advice to other people?

### Hypothesis 4: SIP management friction

Investors may find it hard to change, pause, or cancel a SIP.

Groww has no primary-category lead in this sample for pause, cancellation, amount, date, or setup. Zerodha Coin has 5 amount-or-date leads and 3 setup leads. INDmoney has 1 amount-or-date lead. YouTube has 5 cancellation leads and 1 pause lead, not linked to an app.

Possible product questions:

- Is the wording a request for help, or a statement that the person already changed the SIP?
- Is the journey hard to find in the app, or only hard to describe in a review?
- Does the same complaint appear for Groww once more Groww SIP reviews are read by hand?

## 6. Research gaps

This secondary material cannot answer:

1. How many reviewers or commenters were first-time investors?
2. How many people actually discontinued a SIP?
3. What the primary reason was, when the text does not state one?
4. Whether a stop was permanent or a pause?
5. Whether a stop was a choice or the result of a failed payment?
6. What the person did after stopping?

Those questions need the original text to be read, and they need interviews.

## 7. Proposed user interviews

Talk with 5 or 6 people who started a first mutual fund SIP in the last 1–3 years. Include people who are still investing and people who paused or stopped.

Ask them to describe what they did. Do not ask them to agree with the four hypotheses.

**Background**

1. When did you start your first mutual fund SIP?
2. What led you to start?
3. How did you choose the app and the fund?

**Investment experience**

4. What happened in the first three months?
5. Was there a time you were unsure about continuing?
6. Have you reduced, paused, or stopped an SIP?

**If they paused or stopped**

7. What happened just before that decision?
8. What did you see as the reason: money, returns, the market, a payment problem, or something else?
9. Did you think about starting again?
10. What, if anything, would have helped you continue?

**App experience**

11. Could you tell what the SIP was doing, and could you change it when you wanted to?
12. What, if anything, was confusing or frustrating in the app?

If the person has not paused or stopped, skip questions 7–10 rather than pushing for a discontinuation story.

## 8. Synthesis sheet for validated observations

Use one row only after a person has read the original text or finished an interview. Do not fill this sheet from keyword hits alone.

| Field | What to record |
| --- | --- |
| Original feedback | The review, comment, or interview words. Do not paraphrase over the original. |
| Source | Google Play, YouTube, or interview. |
| Source identifier | Play `source_id`, YouTube `comment_id`, or an interview code. |
| Investor context | Only facts the person stated, such as a start date they gave. Leave blank if they did not say. |
| Observed behaviour | What they said they did: continued, reduced, paused, missed a payment, or stopped. |
| Stated reason | The reason they gave. Leave blank if they did not give one. |
| Emotional context | Words they used about how it felt. Do not add an emotion they did not express. |
| Evidence strength | Strong when they describe their own action; weak when the text is advice, a question, or a general complaint. |
| Groww or broader category | Groww only when the source is a Groww review or the person names Groww. Otherwise mark it as general, or name the app they named. |
| First-time relevance | Relevant only when they said it was a first SIP or a first mutual fund. Otherwise unknown. |

No row in that sheet has been filled yet. The keyword files are the queue for reading, not the finished observations.

## 9. What this stage does not conclude

Groww is the product selected for the assignment. In this Play sample, Groww reviews are mostly positive and rarely mention SIPs. The SIP payment, missed-instalment, and SIP-management leads that the rules found sit mainly on Zerodha Coin. YouTube adds a separate set of missed-payment and stop-or-cancel phrases that are not tied to Groww.

The next evidence step is to read the shortlists, especially the 6 YouTube comments with stop-or-discontinue wording and the 5 with cancellation wording, and then to run the interviews in section 7. Until that reading and those interviews are done, the four hypotheses stay untested.
