# AI Agents & Crypto: What Could Go Wrong

Jean-Loïc Mugnier. Timestamps are from the start of the clip.
Machine transcript (Gemini via OpenRouter), lightly cleaned; names and
products not yet checked against the slides.

**[0:00]** Hello everyone. My name is Jean-Luc and today I'd like to bring you a few cases of incidents that happen in the ecosystem where agents started to play with crypto, right? So, by the end of this presentation, I hope you have understood that, um, the risk associated with running models that touching crypto is not only about the crypto itself, nor about the model.

**[0:30]** group. Um not only about the model and that uh we'll be sharing as well our framework of maybe how to think about the security aspects when you're building an agentic uh system touching crypto. So, a little bit of context about me, um I will skip the rest, but very interesting topic that I would like to address in one of the risks. When AI agents are interacting with crypto, they need to have uh a vision, an interface to understand the data on-chain. And so, our research with

**[1:00]** Ethereum Foundation was proved to show some very interesting results. So, why is uh crypto and AI such a big topic right now? Well, for the past 30 years, the financial market has been having, collecting the data, using algorithms, and everything that was missing was someone to take action upon the that data. So, agents are perfect to fit that role, and it's way simpler to just spin up a model, spin up an agent, and have it interact with

**[1:30]** crypto, in general. But when you want to build a a agentic system, you have to build all the infrastructure, right? You have to build uh to choose the model, to build the infrastructure where the model is hosted, or use uh someone else infrastructure. You need to be able to pull data from on-chain, uh maybe interact with protocols to understand what will be the result in some kind of preview or simulation. And you still have the risk of anything that can happen on-chain, right? The problem with that is

**[2:00]** is that any kind of bug or any kind of mistake is a financial loss. So let's dig a little bit into some of the cases that happened recently. Um, LobstaWild was a project run by, uh, one of the OpenAI employees, now working at Codex. His goal was to run an agent on X, and allow him to trade based on information he would find, right? So, what happened is someone was able to comment on his posts and ask for some funds. Basically,

**[2:30]** agent uh decided to donate for Solanas, but, apparently, the explanation was that reading the interface, it misread the number of digits to send to the user, so, actually, it sent 52 million tokens, which represent uh, more or less, 500,000 at the time. The problem is that there's very hard It's very hard today to be able to explain why an agent took a decision, and it's all about observability inside of

**[3:00]** the agent and this is currently not a big there is no current uh relevant solution for that. A second case uh was an agent, uh a aixbt, that was running on servers, so the user would have uh a control panel where he would submit transactions that would should be executed by the agent. It could be a very interesting way to connect from a distance and submit uh dedicated uh actions for the agent to take into consideration. This time the problem

**[3:30]** was the infrastructure the agent was running in. The count the panel control was actually vulnerable and the hacker was able to submit a request for an approval of funds to his address. So, after being able to send that information the agent gave uh the hacker uh the access to the funds and was able to retrieve all the funds. At the time it was 55 if, so, $100,000. And um basically, the

**[4:00]** infrastructure was uh the responsible uh was responsible for that that vulnerability. The third case I would like to discuss is the next step when the AI agents should try to interact with uh protocols on-chain, try to have some information about what the what uh what they'll be doing, how much tokens they're going to get. So, a best practice today in the industry is to perform a simulation, have a preview of that information, and de-

**[4:30]** whether to proceed or not. However, our research uh for the Ethereum Foundation found a systemic vulnerability where you can have um completely safe simulation that actually ends up draining all your assets from your wallet. So, this is actually a print screen of uh wallet uh preview uh showing the user a completely safe and expected outcome. The user was expecting to get one token back and to give one token away. And actually, this was the result. So, all

**[5:00]** The assets were gone and there was nothing he could do at that moment in time. So why does that happen? Blockchain transactions are they are basically code execution. So when you're signing, you're signing for that code to execute. However, the code itself can change, right? The market can change. The liquidity present in the markets can change. The smart contracts themselves can be upgraded, right? So between the moment the transaction is signed and the transaction is executed,

**[5:30]** takes some time, frame, right? And if a hacker is able to perform changes in the contracts the user is going to interact with, then the outcome can be unpredictable. And that's something that we can have. So, how should we uh So, there There are several ways, right, the industry is trying to address the problem. They're trying to make AI more explainable to provide the observability inside a model, but, as we know,

**[6:00]** Much online data is hard to be trusted, right? What prevents another agent from posting, or a competitor from posting fake data, uh as an article, or even fake data on-chain, right? Some researchers at Google were able to deploy uh malware on-chain that would infect the the browser. So, if we we're thinking about financial services, financial systems that require the most advanced security, we have to trust uh we have to consider

**[6:30]** everything as malicious. This is the Zero Trust model. And so, it's very hard to control everything that the agent reads, and also evaluate how is he thinking, because he's have information that you don't have. Therefore, our approach and our interest for the for the future as a research, to continue understanding uh how um we can better control the agents. Well, not only as a research, but this is actually something that we have live, working.

**[7:00]** Our approach, basically, is, instead of limiting the amount of information or filtering the information, is about controlling what the agent can do. So, there are two things: There are the policies, basically the contracts they interact they can they're allowed to interact with, the tokens they are allowed to interact with. But, also, given the blockchain nature and how transactions can be evaluated inside an EVM, we also deploy what we call, uh, enforcement contracts. So, this

**[7:30]** gives us leverage to be able to evaluate the consequences of the agent actions before they are definite. As you know, crypto transactions, once they settle, they cannot come back. So, that's the last moment when we know exactly what's going to happen and that's the moment when we know if we have to pull the the the plug and decide to revert the transaction not to lose funds or not to go outside the compliance rules, right?

**[8:00]** So, uh that was a little bit of what I want to share, but, uh, always happy to answer any questions afterwards. [applause] Cool. Thanks. Well, wow, you actually like came in at, uh, 8 minutes, very very impressive. Um, yeah, thanks to all the presenters. Uh, let's give them a round of applause again. [applause]

**[8:30]** [cheering] [applause] And uh now we can, yeah, have have some more pizza. Uh, you know, if you want to ask questions to the to the presenters, now's time to do it, also. And just, I want to just say one thing about this space. Um uh so yeah, we're we're here at Full Node. This is the Gnosis office, so Gnosis was uh generous enough to let us be in their office tonight to host this meetup, so big round of applause for Gnosis and Full Node. [cheering] [applause]

**[9:00]** [applause] And uh, yeah. So thanks, Rob. Enjoy.
