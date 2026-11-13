# [Your SaaS Is Becoming an Agent](https://www.youtube.com/watch?v=XX3vqa-PjTk)

Sacha Dumay, co-founder and CTO of Cashflowy. Timestamps are from the start of the clip.
Machine transcript (Gemini via OpenRouter), lightly cleaned; names and
products checked against the slides.

**[0:00]** [clapping] Hello everyone. Um so my name is Sasha. I'm the CEO of Cashflowy. Uh I previously built, when GPT arrived, ChatNode.ai that I sold a year after. And now it's been a year, I'm building basically a booking bookkeeping software uh and your financial partner for US business. So, my goal for today's this talk is to talk about my experience the last year and

**[0:30]** how I see building SaaS going in the future, and especially why we chose at Cashflowy to build our agent, why AI agent on the Eve uh Vercel framework. So does anyone here know Eve framework from Vercel or not? Two, three, four people. Okay, good. So some people will learn something. Uh and does anyone know Vercel? Come on, right? Okay, so first thing again, just to sum up, this year OpenClaw arrived.

**[1:00]** That's that's kind of where we became from GPT just, you know, answer my query from Google to actually do something useful for me. Then we got Instinct. I don't know if anyone know Instinct, I love it. That's my uh personal assistant on WhatsApp. He does my grocery, he does all my email and everything. In US, people use Muse and there is Grokbot. A few of my team member use that for managing the team, email and everything. So that's kind of I think big

**[1:30]** shifts that we think about how we actually, thinking about all these AI assistance, how it challenge, how you build the SaaS. Uh so, just to go back to Cashflowy, we, so the first thing we did is like roughly six, seven months ago, you maybe have seen on SaaS what they do is they say, "Okay, people, everyone talk about AI, let's put some chats in my dashboard, whatever." So you put it as a side panel on the right. So we did that, and some people started

**[2:00]** to use it and we noticed that it was a small sample but people that use the chat to ask questions about how to use a SaaS, how to use Cashflowy, or answer anything, were almost twice as likely more to become a paying user. So we realized that the chat is not a side thing anymore. Like the AI agent's not, you know, you add it on your SaaS. It should become the main thing. So we make the kind of bold decision in some way, not bold anymore, but

**[2:30]** to move the chat to be the center face and any kind of dashboard artifact, kind of you think about your artifact on the cloud, can come up in the chat or on the side. Um and so what's important is now you need to make your AI agent much more powerful because if the chat just answer basic question, no one's gonna use it. So, unfortunately, when we started the chat, I use, I don't know if anyone know TanStack. Uh it's kind of big framework.

**[3:00]** more for React up. We use that, the library for making a- I did the MVP in like a weekend. It was good to have a knowledge base, a few tool, but it live in your browser and so it's really not good for actually eating long-lasting task. Uh, and you know, as a bookkeeping software, running your finance, you need something much more powerful. So, we, um, I started to say, okay, I need a scheduler for deep

**[3:30]** active, I need to add a sandbox, and I'm like, well, I'm not going to do all that, and the code's going to become a mess. That's where I found out about Eve. So it's an open source uh agent framework that kind of if you want to build an agent now and on the entire harness uh and be up to the standard of Muse, Instinct, Grokbot, you kind of need that. Um, so you can take

**[4:00]** the picture if you want or look at Eve. But basically, you need all those components to make a proper, you know, AI agent right now. Maybe in the months it's not going to be that. Um to notice, as a disclaimer, Eve, so was built by um Vercel four months ago, so it's still new, and they change very fast, very a lot because, you know, everything change fast. So, I'm going to just focus on a few of them.

**[4:30]** Uh the good thing is, of course, you need tools. That's where your building blocks of doing task. And in here it's basically the the way this framework is made is you have one big folder and under this folder you have markdown file and sub folder. And that's all. That's your architecture. So for example, for tool, one tool is one TypeScript file. You can use for your MCP, you can use for everything, it's going to be the same file, same code. You don't need to

**[5:00]** reduplicate your code for making the MCP or everything. One thing I liked about this framework was uh especially if you talk about finance data, you want the user to, you know, approve changing category, moving money or something like that. So, the prime is LM are, you know, non-deterministic, so you cannot really rely on LM to say, okay, I'm sure you the users confirm. So, with this,

**[5:30]** more work, you have a way to ask the user approval and it's not by LLM, it's by the code, which is much more reliable. Uh, so they have an amazing simple scheduler with cron. So your user can spin up like, okay, give me a report every week on my finance, my money, et cetera. Um, and another few things that we really love is they have an out-of-the-box sandbox, so

**[6:00]** And on our user case, let's say a user have ten subscription and they want to cancel one. We likely need their credential and a sandbox to open a browser to their subscription and cancel it. So they have that. Also Vercel have a gigantic list of connection. In our user case, you know, it could be Linear, GitHub, so every other tool that you need to make your agent more powerful. In our case, it was Gusto. It's a payroll company in US, and so our

**[6:30]** you can just say I want to add my Gusto and then we reconcile with that navigation. And then we are working for example on having Cashflowy on iMessage. So they have this channel easy template to add it on everything. Uh, the last thing that's always important when you build an agent is your Eval. Uh, because so that's an example of an error we did, we we didn't want the LLM to remember

**[7:00]** So, user is saying, "Oh, I believe the financial layer should be the truth from the database, and we we don't want the user to interfere with that." And so, they have an eval that you I run on the CI every time to make sure that if a user has something or saves some information, the agent is actively doing what it's supposed to do. So, always use an eval for agent. Um, another insight I wanted to say is,

**[7:30]** When we started, I I don't know, I have this old mindset of like, you need workflow. Everyone talk about workflow for years. There is make, make, there is Zapier. I think workflow is so outdated and you should never use workflow anymore. Because, like, look, imagine we had, so some user wanted to import statement. So we you build a workflow, say, okay, this guy needs to import, put a statement, do that, call an LLM. The problem is that it's always

**[8:00]** You're going to duplicate code if you have like 10 workflow. It's going to tell. What you want is have one central AI agent, do under all that with the tool and the sub agent that you need to. And why it's so powerful, it's because as an example, you just say, okay, my business is about uh the law and you know chatty. So the agent learn from that as a memory tool. And then when the categorization happen, in a different, let's say you had a different workflow. Now you don't,

**[8:30]** not a different framework. you just spin up your agent to say, categorise this transaction, and he will know that the context, every all the context that he need, he will have it. So, use one central agent, and dispatch this agent whenever it's need, and add tool and sub agent if you need, and skill. So yeah, we had, just to say that now we have yes, many skill for categorisation and yeah, 47 tool. So, um, you write

**[9:00]** pool and skill and you just let the harness run whatever action or like the old school workflow that you needed. So yeah, build your product, uh not the harness, use this framework. You can, I just started a Substack a few weeks ago, so please uh go check it out and you can connect with me with that. Thank you, if you have any question, let me know. [applause] Then you would pay
