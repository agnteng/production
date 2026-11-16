# Main takeaways

What someone would say they learned at this meetup, from its talks and Q&A.
One per line: `- **Claim.** One or two sentences.`

- **Agents can pay for what they use.** x402 lets an agent pay per request from its own wallet, with no bank account or sign-up, and Cloudflare and AWS already support it.
- **Micropayments make premium data affordable.** Data that normally costs hundreds of dollars cost an agent five cents a query.
- **When agents write the code, review is the bottleneck.** At PostHog agents write 81% of pull requests. Review is now done by agents checking correctness, security and performance, with a judge that fixes the code or escalates to a person.
- **Automate approval, but not everywhere.** Agents can approve changes behind deterministic rules, while anything touching auth, CI or billing always goes to a person. Pull requests got bigger and reverts went down.
- **Agents need constraints more than context.** Keeping coding agents inside a design system came from narrowing what they see and feeding rule violations straight back into their loop. One screen's context fell from 17,000 tokens to about 1,400.
