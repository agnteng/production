### [AI Agents & Crypto: What Could Go Wrong](https://www.youtube.com/watch?v=FlxGA1n5jyY)

Jean-Loïc Mugnier walks through real incidents of AI agents losing funds on-chain and lays out a framework for securing agentic systems that touch crypto.

**Main Takeaways**

*   The risk isn’t just the crypto or the model, it’s the whole stack: infrastructure, on-chain data, the protocols, and any bug becomes a direct financial loss.
*   Lobster Wilde’s trading agent misread digits in an interface and sent 52 million tokens (~$500k); the deeper problem is you can’t explain why an agent decided what it did.
*   aixbt lost 55 ETH (~$100k) not to a model error but to a vulnerable control panel that let an attacker submit a fund-approval request.
*   Transaction simulations aren’t safe by default, since their research with the Ethereum Foundation found a safe-looking preview that drained a wallet because contracts and liquidity can change between signing and execution.
*   Treat everything as malicious (zero trust), and rather than filtering what the agent reads, constrain what it can do with policies and on-chain enforcement contracts that can revert a transaction before it settles.

Jean-Loïc's [X](https://x.com/theFrBrGuy), [LinkedIn](https://www.linkedin.com/in/jeanloicmugnier/)
