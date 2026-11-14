### [One Chat Box, Many Agents](https://www.youtube.com/watch?v=umcpyslKCLY)

Federico Kunze Küllmer breaks down how Moneda built a cheap, context-aware financial support agent benchmarked against Intercom’s AI.

**Main Takeaways**

*   Most support agents fail not because they’re built wrong but because they only have FAQs and a knowledge base, never context about your actual problem.
*   The architecture is a multi-agent flow: input guard, then an orchestrator that classifies the question and reads user sentiment to set the reply tone, then support or companion sub-agents, then an output guard and a tripwire.
*   Build for adversaries, since the tripwire exists to stop scam and refund-extraction attempts where an under-context agent hands money back it shouldn’t.
*   Cost dropped from $1 per resolved conversation to 5-15 cents through model tiering with good-enough models like Kimi, prompt caching, and moving FAQs into a database with embeddings instead of fine-tuning.

Federico's [X](https://x.com/fekunze), [GitHub](https://github.com/fedekunze), [LinkedIn](https://www.linkedin.com/in/fekunze/)
