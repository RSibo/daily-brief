# Active Hot List Themes Registry

This registry defines the living priority themes tracked across Gmail and Google Chat communications.
The `briefing_writer_agent` dynamically reads this file on each run.

### Triage & Reporting Mandates:
1. **Lookback Window:** Trailing 3 days (unread messages only).
2. **Mandatory Reporting:** Every active theme in this table must appear in the morning brief.
3. **Fallback String:** If no unread messages are found within the trailing 3-day window for a theme, the agent must output:
   `On topic [Theme Name] no updates yet.`

| Theme Name | Focus Keywords & Search Syntax | Target Aliases | Lookback & Qualification Rule |
| :--- | :--- | :--- | :--- |
| **Optus VAIS & Model Armor Blocker** | `optus AND (VAIS OR "Vertex Search" OR "Vertex AI Search" OR "Model Armor" OR "Model Armour" OR blocker OR "product ask" OR Bedrock OR Tyrone)` | Optus, Singtel, Tyrone | Past 3 days, unread only; if none: *"On topic Optus VAIS & Model Armor Blocker no updates yet."* |
| **Woolworths (GE, FDE/SWE Initiative, FLW)** | `(woolworths OR woolies) AND (GE OR "Gemini Enterprise" OR FDE OR SWE OR FLW OR "Shopping Agent" OR GECX)` | Woolworths, Woolies | Past 3 days, unread only; if none: *"On topic Woolworths (GE, FDE/SWE Initiative, FLW) no updates yet."* |
| **Google AI DRZ / AU ML Processing** | `(DRZ OR "Data Residency" OR "ML Processing" OR "in-country" OR "in-region") AND (Australia OR "AU" OR "sydney" OR "melbourne" OR "australia-southeast1" OR "australia-southeast2")` | DRZ, ML Processing, AU In-Region | Past 3 days, unread only; if none: *"On topic Google AI DRZ / AU ML Processing no updates yet."* |
