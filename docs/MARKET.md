# Market

## The thesis

Voice is becoming the default interface to AI: assistants, dictation, agents and smart glasses.
But talking out loud is impossible for some people and unwelcome for everyone some of the time. **Silent
speech is the missing input mode for the voice era**, and glasses are the natural place for it: they
already sit a few centimetres from the mouth, and they're the fastest-growing new personal device.

## Who it's for: beachhead → expansion

| Segment | Job to be done | Why now | Entry product |
|---|---|---|---|
| **Care (beachhead)** | People who can't voice speech (laryngectomy, ALS/MND, ventilated ICU patients) need to talk to family and caregivers | Today: slow letter boards and tablets. Setu works with a closed phrase set, which is exactly what our accuracy supports | 20-phrase set + silent phone calls via Bolna, in 11 languages |
| **Prosumer** | Hands-busy, noisy or silence-required work: factory floors, airport aprons, hospital night wards, security, field service | Voice agents and radio already run these workflows, and the user can't speak clearly into them | Command packs per workflow + push-to-call |
| **Consumer** | Talk to AI, reply to messages and take calls in public, in meetings or at night, without being heard | Smart glasses are going mainstream, and dictation is a $2 B category | Silent-input module for smart glasses; phone app with a voice agent subscription |

We start in care because the need is acute and a closed vocabulary already helps. Every care user's
sessions grow the dataset that moves the recogniser toward open vocabulary, the consumer product.

## Numbers (sourced)

| Signal | Figure | Source |
|---|---|---|
| Smart glasses shipments | IDC forecast **13.6 M units in 2026**, **27.3 M by 2030** | IDC via [smartwearables.io](https://www.smartwearables.io/news/smart-glasses-shipments-167-percent-growth-q1-2026-idc-13-million-forecast) *(verify against the IDC release)* |
| Meta smart glasses | EssilorLuxottica sold **> 7 M** Ray-Ban/Oakley Meta glasses in 2025 | secondary, citing the FY2025 disclosure, via [VoxBooster](https://voxbooster.com/blog/smart-glasses-statistics-2026/) *(verify)* |
| Voice input is a venture-scale category | Wispr (Wispr Flow) raised **$280 M at a $2 B valuation**, Aug 2026 | [TechCrunch](https://techcrunch.com/2026/08/17/wispr-raises-280m-at-2b-valuation-as-it-looks-beyond-dictation/) |
| AAC devices (care beachhead) | **$2.34 B in 2025**, 11.9% CAGR | The Business Research Company, via [GII](https://www.giiresearch.com/report/tbrc1710061-augmentative-alternative-communication-aac-devices.html) |
| Silent speech is a recognised category | MIT spin-out AlterEgo launched a neuromuscular silent-speech wearable, Sep 2025 | [Axios](https://www.axios.com/2025/09/08/startup-query-ai-silent-speech-neural-interface) |

*TODO before the deck: patient-population numbers for India (laryngeal cancer incidence, ALS
prevalence, ventilated ICU patients per year) from ICMR / GLOBOCAN. Don't put unsourced numbers on a slide.*

## Positioning

| | Input | Wearable | Works in calls | Indian languages | Privacy |
|---|---|---|---|---|---|
| Voice dictation (e.g. Wispr Flow) | audible speech | no | n/a | partial | others hear you |
| Camera lip reading | video of the face | needs a camera pointed at you | no | no | camera on the face |
| Neuromuscular (AlterEgo-style) | jaw and throat electrodes | dedicated headset | n/a | n/a | good |
| **Setu** | contactless lip motion only | **ordinary glasses frame** | **yes, via a Bolna agent** | **11 output languages** | **no camera, no mic** |

## Business model (hypotheses to test)

* **Care:** device + monthly subscription (voice-agent minutes, languages, caregiver app), sold
  through hospitals, ENT and oncology centres and insurers. The call-relay feature uses Bolna minutes, so
  revenue scales with usage.
* **Consumer and prosumer:** license the silent-speech module and model to smart-glasses makers
  (per-unit royalty), plus a consumer app subscription for the voice agent.
