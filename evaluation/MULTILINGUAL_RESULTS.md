# English and mixed-language results

Measured 2026-10-11T06:50:46.519384+00:00 on 18 original synthetic PDFs ([manifest](multilingual_manifest.json), [generator](generate_multilingual.py), [raw](multilingual_results.json)).

**These are development fixtures written together with the English extraction rules. They show the rules work as designed; they are not a blind or real-world accuracy estimate.**

| Mode requested → used | Group | Labels | Status accuracy | Precision on answered | Conflict precision | Conflict recall | Abstention | Median / max s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| lexical → lexical | en | 42 | 97.6% | 100.0% | 100.0% | 100.0% | 11.9% | 0.28 / 0.31 |
| lexical → lexical | mixed | 12 | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.28 / 0.31 |
| lexical → lexical | all | 54 | 98.1% | 100.0% | 100.0% | 100.0% | 9.3% | 0.28 / 0.31 |
| hybrid → hybrid | en | 42 | 97.6% | 100.0% | 100.0% | 100.0% | 11.9% | 0.62 / 0.86 |
| hybrid → hybrid | mixed | 12 | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.62 / 0.86 |
| hybrid → hybrid | all | 54 | 98.1% | 100.0% | 100.0% | 100.0% | 9.3% | 0.62 / 0.86 |

## Disagreements with the designed label

- lexical: `en-a_wrong_trigger` OSAGO_PAYMENT: expected UNVERIFIABLE, got NOT_FOUND
- hybrid: `en-a_wrong_trigger` OSAGO_PAYMENT: expected UNVERIFIABLE, got NOT_FOUND

`en-a_wrong_trigger` is labelled UNVERIFIABLE (a deadline exists but counts from the accident). The engine returns NOT_FOUND because its payment-clause topic requires the insurer's decision, the same design as for Russian and Uzbek. Either way no comparison is made; the wording shown to the user differs.
