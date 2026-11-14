# What The Hell Is An Agent?

Misha Kolesnik. Timestamps are from the start of the clip.
Machine transcript (Gemini via OpenRouter), lightly cleaned; names and
products not yet checked against the slides.

**[0:00]** Uh I wanted to start with something Thank you. I wanted to start with something real really simple, but uh I'm sure that if I will ask two people in this room, I won't hear the same answer. Like, certainly. And even if it it seems so obvious, it's still, I think, the like complex question of what an agent actually is.

**[0:30]** and what components it should have to be called an agent. Uh, how do you, like, define and what you need to provide to it to be the thing that it is. Uh, I want to go, like, through the whole path with you, starting with the simple LLM API. That's where you start with when you want to build an agent and you want to make it do something. You just get some API endpoint

**[1:00]** and you try like throw-in requests at it. But the first problem you arrive at is the lack of persistence. It just cannot like remember anything if you won't build the persistence yourself and uh provided away to preserve context between every request. So right now we added sessions and now our agent can respond and can remember what it responded. Is that an agent?

**[1:30]** My answer is that it, it's not. It lacks uh, many [laughter] many components uh, that uh, actually would make it useful. The core problem uh, that I see on this stage is that uh, an agent can not access any data or do like anything uh, besides what you will send to it in request or what it will see in the prior context of the conversation

**[2:00]** So, it obviously needs tools. It needs something to access information on its own, uh, from the outside world and not only from the data it already learned on. Uh, with tools, there are like two issues. Uh, the first one is that, uh, you can provide it like with

**[2:30]** all the tools that it may need. But the problem is that you will never build enough. There is always will be a task that you cannot like cover and you cannot build the indefinite amount of tools. The second issue that even if you like do the tools, it will be Okay, probably I wanted more to say about that it's not enough just to like

**[3:00]** give the agent tools, but also, it's [laughter] important to give it possibility to, ah, um, how I'd say, to do its, like, act of agency, to gain the agency. It's not enough for it just to send JSONs and get response from the tools. The important part is that we need to allow agent to build the tool itself. And that's where, um, Claude Code got its popularity

**[3:30]** Uh, in the, at first, uh, because like the mainly, we, but the main value proposition that it brought that hasn't existed before was that it had given very simple tools to an agent, bash tools, or like something that it can execute and uh do it in a flexible way. So basically, an agent got the possibility to uh build its own tool and run it, execute it, and not operate only on the

**[4:00]** data within its context, but rather operate on the bigger chunks of data. Uh, meaning that if it needs to analyze data, uh, it doesn't have to get all the data in its context and then try to uh do some operations top of it, because it's like literally impossible. It needs some more efficient ways, and agent uh needs ways to do some

**[4:30]** it without you actually specifying every step of how it should do it, or doing everything for itself. Uh, the the next part, even with, uh, if you provide it with tools, you provide it with possibility to execute some operation, it, uh, analyzes the data, uh, but then like, uh, agent still needs to have, uh, to persist some kind of context be- between the conver-

**[5:00]** sessions. Because even if you store sessions, we all know that you cannot pull all of these sessions in the context of an agent and expect it like to know and remember everything and to bear all of those resources it needs to operate on in its context. It needs some persistent layer. Uh, resources. So, for example, like GitHub repository. You need pro- to provide a way for it to easily a-

**[5:30]** access it, uh, operate on it. Uh, basically in Claude Code, that, uh, that's a file system. That's a file system that agent operates on and that exists between the, like, uh, between different operations. Even if you will change the sandbox or some other component, uh, you always know that the there is like some specific state that you can continue operating on, which is resources. And, uh,

**[6:00]** The next thing without which the agent just doesn't work. Uh, you have the LLM API, uh, you gave it tools, gave it the possibility to execute those tools. Uh, you also gave it the possibility to, uh, store some content between different conversation turns. Uh, still there should be some engine that would be handling complex operations for a model. A model

**[6:30]** can produce a JSON that will, uh, that will be a tool call, but it cannot execute the tool call itself. There should be some mechanism that will read that this JSON means a tool call. It needs to execute it and provide the feedback back, or it needs, uh, [laughter] to nudge an agent to do something if it hasn't, like, solved. It has to operate actually, uh, the more longer r-

**[7:00]** in turns. And, uh, at some point, uh, I've thought myself that it's enough, uh, that, okay, you have LLM API, you have sessions, you have tools, you have resources that you provide to an agent, you have harness, uh, that's it. Uh, but there is a core distinction and, uh, why you can call OpenClaw an agent, but

**[7:30]** but you probably can't call Claude Code or Codex an agent. That's its possibility to persist and keep doing stuff even when you are not behind your laptop. That its possibility to live [laughter] without you continuously nudging it, to remember things, to run something on schedule, to uh basically like not just finish the the job and

**[8:00]** and then die. But to actually do something on the background. And that's layer, that's orchestration. And that's what OpenCore brought as the latest bit for something that I see as a complete kind of set of components or set of core pillars, without which, uh, you cannot call the thing that you see an agent. It's just a function call. For it to actually

**[8:30]** to be an agent you need to have all of those components uh for it to be able to execute the agency. Uh this picture like that helped me to arrive finally on that idea uh and how to actually distinct those components, how to define them, and how like to understand where is the where are the boundaries between those components. That's from the Managed Agents blog post

**[9:00]** posts uh on the release from Anthropic. I think that they have covered the core components very well, and uh probably the core thing or the core elegance about this distinction is that each component can evolve on its own, because that's uh one of, another uh key thing that [cough] uh that we've seen that uh nothing stops evolving,

**[9:30]** In the agentic wor- wait. In the agentic yeah, world. [laughter] Every Everything, every bit, sessions evolve, sandboxes continuously evolve, the way we use tools, the way we orchestrate, the harnesses, everything, like, is swappable, and it has to be able to evolve in isolation from the other components. And that's what allows it. [laughter] That's it. [applause]

**[10:00]** [applause] Cool. Thanks. Uh, do we have any questions? I have a question. Which, um, what what is the the like the best agent do you think that implements all of these things uh to the like its best abilities? Mm, okay. [clears throat]

**[10:30]** Basically like I've seen the complete, uh, that complete architecture only from Anthropic. I've seen what, uh, OpenAI has tried to do in response to that release. Uh, it's interesting, but it doesn't feel as coherent and complete, and it doesn't feel like it was coming from the actual necessity or the experience. Uh, with Anthropic, what I'm like seeing is that what they've de-

**[11:00]** client was all called by the requests from their enterprise clients. Because all of those components, why they have to be distinct and separate? Because you need to allow for, uh, building in a proper security hardening, the proper, like, ways to isolate the workloads, and else, and else, and else. And

**[11:30]** That's something that I haven't seen any other framework achieving yet. And I'm not seeing like their product as the one to use. I'm more uh liking their approach and I think that's something that should be slowly implemented in open source. Okay, cool. Thank you.
