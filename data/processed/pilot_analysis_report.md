# SIP pilot analysis

This is an exploratory analysis of a 100-record pilot. It is not the final research conclusion. The counts describe only the rows in `classified_records_pilot.csv`. They are not a statistically representative sample of SIP investors, and they do not show that one factor causes another.

## Counts

- Total classified records: 100

### Source
- YouTube: 77
- Google Play: 23

### App
YouTube rows in this file have a blank app cell. Those rows are counted as blank rather than assigned to an app.
- (blank): 77
- Zerodha Coin: 19
- INDmoney: 3
- Groww: 1

### SIP relevance
- direct: 64
- indirect: 35
- not_relevant: 1

### Behaviour
- general_advice_or_opinion: 64
- unknown: 33
- missed_installment: 2
- actively_continuing: 1

### Root cause category
- unknown: 99
- payment_failure_or_technical_friction: 1

### Emotion
- neutral: 50
- positive: 29
- negative: 20
- mixed: 1

### Continuation relevance
- general_discussion: 95
- missed_instalment: 3
- not_applicable: 1
- intention_to_discontinue: 1

### Evidence strength
- moderate: 64
- none: 33
- strong: 3

- Average confidence score: 0.867 across 100 numeric scores.
- Records with unknown root cause detail: 96
- Records with unsupported inference flagged true: 45

## Comments about SIP continuation friction

The four continuation groups below use only the behaviour and continuation labels already stored in the pilot file. Advice such as "don't stop your SIP" is not listed as discontinuation. If a group has no rows, that label does not appear in this pilot. Source URLs are copied from the file. An empty Google Play source_url cell is reported as not present.

Comments shown: 6. This pilot does not contain 10 comments that the stored labels separate into discontinuation, intention, missed instalments, or amount reduction.

### Actual discontinuation
No records in this pilot have this label.

### Intention to discontinue
1. Record `local-08043d83111e20a9`
   - Source: YouTube
   - App: (blank)
   - Behaviour: unknown
   - Continuation relevance: intention_to_discontinue
   - Evidence strength: none
   - Evidence quote: I don’t know if I should sell everything, sit and just wait
   - Source URL: https://www.youtube.com/watch?v=Hk-_40wiLqY
   - Original text:

```text
I have a 3 fund portfolio consisting of 33% S&P, 33% Total stock, and 33% international. I feel a need to focus on complete growth so I went 100% stocks, but does the SP500 and TSM overlap too much to make sense holding both? However I’ve been in the red for a month now. I work hard for my money, so investing is making me a nervous sad wreck. I don’t know if I should sell everything, sit and just wait but watching my portfolio dwindle away is such an eye -sore.
```

### Missed instalments
1. Record `00c521c4-dff3-4627-aa1a-240367c433a8`
   - Source: Google Play
   - App: Zerodha Coin
   - Behaviour: missed_installment
   - Continuation relevance: missed_instalment
   - Evidence strength: strong
   - Evidence quote: Unable to do SIP payment.
   - Source URL: Not present in classified_records_pilot.csv
   - Original text:

```text
Unable to do SIP payment. please check.
```

2. Record `17349479-d93e-4724-90d5-5c8e8efcc807`
   - Source: Google Play
   - App: Zerodha Coin
   - Behaviour: missed_installment
   - Continuation relevance: missed_instalment
   - Evidence strength: strong
   - Evidence quote: I missed my payment this month becoz of this.
   - Source URL: Not present in classified_records_pilot.csv
   - Original text:

```text
I am not getting option to pay next installment of SIP is this glitch or app is dead? it was working fine earlier. I missed my payment this month becoz of this. Hopefully this has alternative not sure what is the issue
```

3. Record `07cc8fde-a222-4581-8ee3-11c6d48f5fc1`
   - Source: Google Play
   - App: Zerodha Coin
   - Behaviour: unknown
   - Continuation relevance: missed_instalment
   - Evidence strength: none
   - Evidence quote: kya matlab autopay ka jab khud hi pay krna pdta hai
   - Source URL: Not present in classified_records_pilot.csv
   - Original text:

```text
kya matlab autopay ka jab khud hi pay krna pdta hai
```

### Amount reduction
No records in this pilot have this label.

### Payment operations, not labelled as discontinuation
1. Record `07e93014-5342-4346-9259-3403f726c457`
   - Source: Google Play
   - App: Zerodha Coin
   - Behaviour: general_advice_or_opinion
   - Continuation relevance: general_discussion
   - Evidence strength: moderate
   - Evidence quote: Coin is not sending mobile notification when an SIP order is ready for payment.
   - Source URL: Not present in classified_records_pilot.csv
   - Original text:

```text
Waiting since 2 years. No update on this feature. Coin is not sending mobile notification when an SIP order is ready for payment.
```

2. Record `16f309bd-d14a-48b9-b845-196e7a4d80f3`
   - Source: Google Play
   - App: Zerodha Coin
   - Behaviour: general_advice_or_opinion
   - Continuation relevance: general_discussion
   - Evidence strength: moderate
   - Evidence quote: it is very hard to find the payment due AMC SIPs
   - Source URL: Not present in classified_records_pilot.csv
   - Original text:

```text
With the change in the recent update made it is very hard to find the payment due AMC SIPs. Earlier it was good the dashboard only was directly showing pending SIPs.
```

A stored label with evidence strength `none` is not treated as proof that a SIP was stopped or missed. Payment-operation comments keep the behaviour label stored in the file.

No generic SIP comments were added to reach 10.
