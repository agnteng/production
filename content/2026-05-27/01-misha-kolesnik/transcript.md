# What The Hell Is An Agent?

Misha Kolesnik. Timestamps are from the start of the clip.
Machine transcript (Gemini via OpenRouter), lightly cleaned and grammar-corrected; names and
products not yet checked against the slides.

**[0:00]** I wanted to start with something Thank you. I wanted to start with something real really simple, but I'm sure that if I will ask two people in this room, I won't hear the same answer. Like, certainly. And even if it seems so obvious, it's still, I think, the like complex question of what an agent actually is.

**[0:30]** and what components it should have to be called an agent. How do you, like, define and what you need to provide to it to be the thing that it is. I want to go, like, through the whole path with you, starting with the simple LLM API. That's where you start with when you want to build an agent and you want to make it do something. You just get some API endpoint

**[1:00]** and you try like throwing requests at it. But the first problem you arrive at is the lack of persistence. It just cannot like remember anything if you won't build the persistence yourself and provide a way to preserve context between every request. So right now we added sessions and now our agent can respond and can remember what it responded. Is that an agent?

**[1:30]** My answer is that it's not. It lacks many components that actually would make it useful. The core problem that I see on this stage is that an agent can not access any data or do like anything besides what you will send to it in a request or what it will see in the prior context of the conversation

**[2:00]** So, it obviously needs tools. It needs something to access information on its own, from the outside world and not only from the data it already learned on. With tools, there are like two issues. The first one is that, you can provide it like with

**[2:30]** all the tools that it may need. But the problem is that you will never build enough. There always will be a task that you cannot like cover and you cannot build an indefinite amount of tools. The second issue that even if you like do the tools, it will be Okay, probably I wanted more to say about that it's not enough just to like

**[3:00]** give the agent tools, but also, it's important to give it the possibility to, ah, how I'd say, to do its, like, act of agency, to gain the agency. It's not enough for it just to send JSONs and get a response from the tools. The important part is that we need to allow the agent to build the tool itself. And that's where, Claude Code got its popularity

**[3:30]** In the, at first, because like the mainly, we, but the main value proposition that it brought that hasn't existed before was that it had given very simple tools to an agent, bash tools, or like something that it can execute and do it in a flexible way. So basically, an agent got the possibility to build its own tool and run it, execute it, and not operate only on the

**[4:00]** data within its context, but rather operate on the bigger chunks of data. Meaning that if it needs to analyze data, it doesn't have to get all the data in its context and then try to do some operations top of it, because it's like literally impossible. It needs some more efficient ways, and an agent needs ways to do some

**[4:30]** it without you actually specifying every step of how it should do it, or doing everything for itself. The next part, even with, if you provide it with tools, you provide it with the possibility to execute some operation, it, analyzes the data, but then like, the agent still needs to have, to persist some kind of context be- between the conver-

**[5:00]** sessions. Because even if you store sessions, we all know that you cannot pull all of these sessions in the context of an agent and expect it like to know and remember everything and to bear all of those resources it needs to operate on in its context. It needs some persistent layer. Resources. So, for example, like a GitHub repository. You need pro- to provide a way for it to easily a-

**[5:30]** access it, operate on it. Basically in Claude Code, that, that's a file system. That's a file system that the agent operates on and that exists between the, like, between different operations. Even if you will change the sandbox or some other component, you always know that the there is like some specific state that you can continue operating on, which is resources. And,

**[6:00]** The next thing without which the agent just doesn't work. You have the LLM API, you gave it tools, gave it the possibility to execute those tools. You also gave it the possibility to, store some content between different conversation turns. Still there should be some engine that would be handling complex operations for a model. A model

**[6:30]** can produce a JSON that will, that will be a tool call, but it cannot execute the tool call itself. There should be some mechanism that will read that this JSON means a tool call. It needs to execute it and provide the feedback back, or it needs, to nudge an agent to do something if it hasn't, like, solved. It has to operate actually, the more longer r-

**[7:00]** in turns. And, at some point, I've thought myself that it's enough, that, okay, you have an LLM API, you have sessions, you have tools, you have resources that you provide to an agent, you have a harness, that's it. But there is a core distinction and, why you can call OpenClaw an agent, but

**[7:30]** but you probably can't call Claude Code or Codex an agent. That's its possibility to persist and keep doing stuff even when you are not behind your laptop. That's its possibility to live without you continuously nudging it, to remember things, to run something on schedule, to basically like not just finish the job and

**[8:00]** and then die. But to actually do something on the background. And that's the layer, that's orchestration. And that's what OpenCore brought as the latest bit for something that I see as a complete kind of set of components or set of core pillars, without which, you cannot call the thing that you see an agent. It's just a function call. For it to actually

**[8:30]** to be an agent you need to have all of those components for it to be able to execute the agency. This picture like that helped me to arrive finally on that idea and how to actually distinct those components, how to define them, and how like to understand where is the where are the boundaries between those components. That's from the Managed Agents blog post

**[9:00]** posts on the release from Anthropic. I think that they have covered the core components very well, and probably the core thing or the core elegance about this distinction is that each component can evolve on its own, because that's one of, another key thing that that we've seen that nothing stops evolving,

**[9:30]** In the agentic wor- wait. In the agentic yeah, world. Every Everything, every bit, sessions evolve, sandboxes continuously evolve, the way we use tools, the way we orchestrate, the harnesses, everything, like, is swappable, and it has to be able to evolve in isolation from the other components. And that's what allows it. That's it.

**[10:00]** Cool. Thanks. Do we have any questions? I have a question. Which, what is the like the best agent do you think that implements all of these things to the like its best abilities? Okay.

**[10:30]** Basically like I've seen the complete, that complete architecture only from Anthropic. I've seen what, OpenAI has tried to do in response to that release. It's interesting, but it doesn't feel as coherent and complete, and it doesn't feel like it was coming from the actual necessity or the experience. With Anthropic, what I'm like seeing is that what they've de-

**[11:00]** client was all called by the requests from their enterprise clients. Because all of those components, why they have to be distinct and separate? Because you need to allow for, building in a proper security hardening, the proper, like, ways to isolate the workloads, and else, and else, and else. And

**[11:30]** That's something that I haven't seen any other framework achieving yet. And I'm not seeing like their product as the one to use. I'm more liking their approach and I think that's something that should be slowly implemented in open source. Okay, cool. Thank you.
