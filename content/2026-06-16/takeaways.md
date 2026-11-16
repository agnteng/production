# Main takeaways

What someone would say they learned at this meetup, from its talks and Q&A.
One per line: `- **Claim.** One or two sentences.`

- **When a coding agent fails, give it a way to see.** Agents often fail because they can't observe the result, not because they lack intelligence. A check that compares their output with the target and says exactly what's off solves what hours of prompting didn't.
- **Evaluate the whole trace, then optimise.** For conversational agents, check every step and tool call, not just the final answer, before working on latency and cost.
- **Context matters more than the model for support.** Support bots fail because they don't know the customer. Routing each question by type and mood, with good-enough models, caching and an FAQ index, took one team from $1 to 5–15 cents a conversation.
- **Assume your agent will be tricked.** Put hard stops outside the model on anything that moves money, such as refunds.
- **When agents hold money, trust nothing.** On-chain, every mistake is a loss: one agent misread the digits and sent 52 million tokens. Many losses come from the systems around the model, so limit what an agent can sign with policies that reject bad transactions.
