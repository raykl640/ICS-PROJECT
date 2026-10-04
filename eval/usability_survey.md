# HakiAI usability survey

Participant ID: ________   Date: ________   Language used (EN / SW): ____

Each participant answers Part A, uses HakiAI on two or three legal questions of their own, then answers Parts B and C.
Enter the answers in `eval/usability_responses.csv` (copy `usability_responses.template.csv`); every answer is a
number from 1 to 5. Do not record names or the questions participants asked.

## Part A: before using HakiAI

**confidence_before.** How confident are you that you understand your legal rights in an everyday problem
(employment, renting, buying goods, dealing with the police)?

1 = not at all confident · 2 · 3 · 4 · 5 = very confident

## Part B: after using HakiAI

**confidence_after.** How confident are you now that you understand your legal rights for the problem you asked about?

1 = not at all confident · 2 · 3 · 4 · 5 = very confident

**clarity.** The answers were written in language I could understand.

1 = strongly disagree · 2 · 3 · 4 · 5 = strongly agree

**usefulness.** The answers (rights, steps and letter) would help me act on my problem.

1 = strongly disagree · 2 · 3 · 4 · 5 = strongly agree

## Part C: System Usability Scale (SUS)

For each statement, choose 1 (strongly disagree) to 5 (strongly agree). Answer every item; if unsure, choose 3.
Wording is the standard SUS (Brooke, 1996), with "system" meaning HakiAI.

| # | Statement | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| sus_1 | I think that I would like to use this system frequently. | | | | | |
| sus_2 | I found the system unnecessarily complex. | | | | | |
| sus_3 | I thought the system was easy to use. | | | | | |
| sus_4 | I think that I would need the support of a technical person to be able to use this system. | | | | | |
| sus_5 | I found the various functions in this system were well integrated. | | | | | |
| sus_6 | I thought there was too much inconsistency in this system. | | | | | |
| sus_7 | I would imagine that most people would learn to use this system very quickly. | | | | | |
| sus_8 | I found the system very cumbersome to use. | | | | | |
| sus_9 | I felt very confident using the system. | | | | | |
| sus_10 | I needed to learn a lot of things before I could get going with this system. | | | | | |

Scoring (done by `python eval/analyze_usability.py`): odd items score (answer - 1), even items (5 - answer); the sum
x 2.5 gives 0-100. 68 is the commonly cited average.

## Optional comments

What was most helpful? What was confusing? (Free text; keep it out of the CSV if it identifies the participant.)
