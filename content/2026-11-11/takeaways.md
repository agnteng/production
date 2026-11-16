# Main takeaways

What someone would say they learned at this meetup, from its talks and Q&A.
One per line: `- **Claim.** One or two sentences.`

- **Cheap AI tokens are a grey market.** Resold credits and accounts can save up to 55%, but you may get a different model, pay more for cached tokens or have your prompts harvested. Use them only for work that isn't sensitive.
- **Agents need to know why, not just what.** Recording each architecture decision gives agents the reasons behind odd code. One team writes about one a day, and the agent now proposes most of them itself.
- **Write the spec before the code.** With a solid specification, the model works like a compiler from English to code.
- **One central agent beats a pile of workflows.** Workflows are fine for an MVP but break when a task is slightly different. One agent with many tools at the centre of the product is easier to maintain, and users who talk to it are more likely to pay.
- **Keep approvals and the source of truth in code.** Let the agent decide, but run user approvals and writes to critical data through deterministic code, and ship a new model only if it passes the evals.
