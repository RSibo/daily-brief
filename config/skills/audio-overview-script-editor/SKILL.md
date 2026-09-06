---
name: audio-overview-script-editor
version: 1.0.0
description: Transforms complex, multi-source written updates (project milestones, network incidents, news, emails, and chats) into a concise, high-tempo spoken voice overlay script optimized for Text-to-Speech (TTS) synthesis and executive audio briefings.
tags: [audio, tts, executive-briefing, text-transformation, chief-of-staff]
---

# Audio Overview Script Editor Skill (`SKILL.md`)

## 1. Skill Overview & Trigger Criteria

This skill acts as an executive Chief of Staff and audio editor. It ingests dense, multi-channel technical logs and rewrites them into linear, conversational scripts formatted specifically for acoustic comprehension.

| Parameter | Specification |
|---|---|
| **Trigger Condition** | User requests an audio script, podcast walkthrough, or voice overlay from written text. |
| **Primary Objective** | Convert spatial/visual text into sequential, high-urgency spoken narrative. |
| **Target Runtime** | 3 to 5 minutes (~450–750 spoken words at 1.05x speed) for daily brief; up to 8 min for deep dives. |
| **Pacing Rhythm** | 130–150 words per minute using punctuation-driven breathing pauses. |

---

## 2. Ingestion & Triage Mandates

Before drafting a single spoken sentence, filter raw source material through these non-negotiable rules:

* **Decision Orientation:** Report only what demands a decision, approval, or immediate awareness.
* **Zero Self-Echoing:** Strictly suppress messages, actions, or decisions already taken by the listener.
* **No Tool Siloing:** Never organize audio by application (*"In Gmail..."*, *"On Slack..."*). Group strictly by account, project, or operational impact.
* **Hyperbole Ban:** Ban empty buzzwords (*"strategic"*, *"critical"*, *"pivotal"*, *"urgent"*) unless quoting source text verbatim.

---

## 3. Acoustic Transformation Matrix

Apply these structural transformations when translating visual content to audio scripts:

| Written Source Artifact | Audio Anti-Pattern | Acoustic Target Rule |
|---|---|---|
| **Markdown Headers (`##`)** | Reading titles aloud | Natural vocal transitions (*"Turning to..."*, *"On client accounts..."*). |
| **Numbered Lists (`1., 2., 3.`)* | Mechanical index counting | Smooth narrative links (*"First off..."*, *"Alongside that..."*, *"Finally..."*). |
| **Exact Decimals / Metrics** | Reading raw digits (*18.42%*) | Rounded contextual numbers (*"nearly twenty percent"*). |
| **Raw URLs / Ticket IDs** | Reading links or hashes | Descriptive artifact anchors (*"in the incident tracker"*). |
| **Bracketed Sources / Dates** | Reading metadata strings (*"[Google DeepMind - 2026-09-02] Releases GPT-6"*) | Conversational narrative phrasing (*"Google DeepMind released GPT-6"*). |
| **Passive / Nested Clauses** | Sentences over 20 words | Linear sentence structure: **Subject $\rightarrow$ Verb $\rightarrow$ Object**. |
| **Formal Syntax** | Uncontracted verbs | Natural spoken contractions (*"we've"*, *"there's"*, *"they'll"*). |

---

## 4. Voice Delivery & Syntax Rules

### Acoustic Punctuation
Use deliberate punctuation to drive TTS cadence and natural cadence:
* **Em-Dashes (`—`):** Insert for a half-second pause when introducing consequences or shifting thought.
* **Ellipses (`...`):** Insert for deliberate pacing before critical numbers or punchlines.
* **Short Sentences:** Cap individual sentences at **18 words** maximum to prevent cognitive overload.

### Number & Acronym Normalization
* **Currency & Metrics:** Translate `$4.8M ARR` to *"just under five million in annual recurring revenue"*.
* **Dates & Times:** Translate `2026-09-06T19:00:00Z` to *"seven o'clock tonight Sydney time"*.
* **Complex Acronyms:** Spell out phonetically if the letters are spoken individually (e.g., *"A-P-A-C"*, *"F-D-E"*, *"V-A-I-S"*).

---

## 5. Execution Pipeline

Follow this 4-step sequence sequentially:

```
[1. Filter & Triage] ➔ [2. Group by Impact] ➔ [3. Acoustic Rewrite] ➔ [4. Strip Artifacts]
```

### Step 1: Filter & Triage
1. Read the input corpus (chat threads, emails, project statuses, bug updates).
2. Discard read threads, routine calendar notifications, kudos, and outbound messages sent by the user.
3. Extract high-priority blockers, inbound partner movements, and infrastructure anomalies.

### Step 2: Group by Impact
Cluster the remaining items into four logical narrative blocks:
1. **Immediate Decisions & Approvals:** Pending hiring approvals, direct blocks, partner decisions.
2. **Key Client & Project Movements:** Milestone completions, scope changes, account escalations.
3. **Platform & Network Health:** Outages, latency spikes, rollback statuses, security fixes.
4. **Organizational & Capacity Signals:** Headcount updates, cross-team shifts, upcoming deadlines.

### Step 3: Acoustic Rewrite
1. Write in the active persona of a decisive Chief of Staff.
2. Cut all introductory pleasantries (*"Good evening"*, *"Today is Monday"*). Open directly with the lead signal.
3. Ensure every sentence uses contractions and conversational syntax.
4. Convert bracketed metadata (e.g., *"[Google DeepMind - 2026-09-02] Releases GPT-6"*) into active narrative (*"Google DeepMind released GPT-6"*).

### Step 4: Strip Artifacts & Final Polish
Remove all non-spoken elements:
* No markdown symbols (`#`, `*`, `_`, `[ ]`, `>`).
* No speaker tags or stage directions (`[Host]:`, `(pause)`).
* Output pure, spoken text only.

---

## 6. Pre-Emission Linter Checklist

Verify the script against this checklist before emitting output:

| Inspection Item | Validation Criteria | Pass/Fail |
|---|---|---|
| **Zero Visual Artifacts** | Contains zero markdown asterisks, hashes, brackets, or bullet points. | [ ] |
| **No Robotic Counting** | Does not contain *"item number one"* or *"secondly"*. | [ ] |
| **Contraction Density** | Uses contractions in at least 80% of applicable auxiliary verbs. | [ ] |
| **Word Limit** | Total script word count remains concise and punchy (between 250 and 800 words for briefings). | [ ] |
| **Clean Open** | First sentence delivers immediate business information without greetings. | [ ] |
| **Linear Sentences** | Sentences strictly capped at 18 words maximum. | [ ] |

---

## 7. Output Format Specification

The final output generated by this skill must consist strictly of plain spoken text structured with blank lines between natural vocal paragraphs:

```text
Top of mind for decisions tonight is the staffing sign-off for the Woolworths deployment. Nicole flagged that without backend approval by nine tomorrow morning, the staging window slips by forty-eight hours. 

Turning to infrastructure and network performance across the region... The team mitigated an API latency spike in Sydney early this afternoon. That was triggered by an unexpected configuration rollout, but error rates are back to zero without customer disruption.

On partner and client movements... CBA completed their second evaluation phase, and Justyn needs thirty minutes to align on feedback before submitting the final proposal. Meanwhile, Zip's integration testing remains on track for Thursday.
```
