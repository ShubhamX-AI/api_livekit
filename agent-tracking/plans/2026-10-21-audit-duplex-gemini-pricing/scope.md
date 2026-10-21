# Scope — 2026-10-21-audit-duplex-gemini-pricing

- **Type:** audit
- **Requested by:** Shubham Halder (backend engineer)
- **Date:** 2026-10-21

## Original request (verbatim)

> I wanted to take a look into the new models, or the last few comments of the new models that you have added, like the duplex and the other things, and the pricing and all those things, like the Gemini models and other things.
>
> Let's start with the duplex part. In duplex, have you checked with Livekit MCP that all the settings that you are taking here are taken there too, and the backend model is taking them? The thing is, after the call ends, are you sending the pricing, or are you calculating the pricing of the backend model and adding it with the GPT Live one or not?
>
> Then let's come to the Gemini part: Gemini models that you have added here. How is it working? Are you properly calculating the Gemini real-time models and all those things, the pricing and everything, and the settings? Is it not causing errors, any kind of errors, and are all the settings done properly or not?
>
> Please take a look and tell me, because there are some issues. First of all, in this duplex, in the call-end call log, we are not getting the pricing of the backend model. I think that also needs to be added and shown. For Gemini, I think some is causing an error. Please take a look once and tell me.

## Agreed scope

| Question | Answer |
|----------|--------|
| Target (paths / endpoints / diff) | Commits cd144d9 + 8d16332 and code they touch (llm/factory.py, session.py, usage.py, core/pricing/, llm_config.py, assistant_guard.py, end-call webhook, CallRecord) |
| Depth (quick / standard / deep) | deep |
| Out of scope | pipeline/cascade modes, Exotel SIP, docs wording |
| Constraints | report-only; no code changes; no new deps; no DB/live calls |
| Success criteria | each user question answered with file:line evidence; severity-ranked findings |
| Report format (HTML / MD) | HTML |
| Severity cut-off | all |
| Type-specific answers | audit only, no patches; no Gemini error string supplied (user: "some is causing an error") |

## Assumptions confirmed with the user

-

## Clarification log

| Question asked | User's answer |
|----------------|---------------|
| Target: commits 8d16332 (Gemini 3.8 + pricing) and cd144d9 (duplex/GPT-6), or wider? | use defaults |
| Depth: standard vs deep (trace usage -> UsageRecord -> webhook/CallRecord)? | use defaults |
| Audit only, or also propose patches? | use defaults |
| Gemini error: do you have an error string / assistant id / model name? | use defaults |
