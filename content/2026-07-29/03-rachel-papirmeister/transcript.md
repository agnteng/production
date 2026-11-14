# Mind as Model

Rachel Papirmeister. Timestamps are from the start of the clip.
Machine transcript (Gemini via OpenRouter), lightly cleaned; names and
products not yet checked against the slides.

**[0:00]** Oh, yeah. All right. Hi, everyone. My name's Rachel Papermeister. I'm a neurosymbolic AI researcher from Columbia University. I work with the Barnard Programming Languages Lab. My advisor is right there and some colleagues of mine. Thanks for coming. Okay. Cool. How do I get over? So, I'm going to talk to you, ooh. Okay, there we go. I'm going to talk to you about Mind as Model: Lessons from human reasoning for flexible neurosymbolic AI. So, most of the AI

**[0:30]** we encounter today relies on transformers, whether it's deep learning, large language models, and all of these, underneath these, what underlies them are neural networks. Neural networks, as a lot of you probably know, learn by incrementally adjusting weights over massive datasets. And this is really good because it offers us generalizability in many different areas. So, if AI develops a skill in one problem space, it's able to it's able to transfer that to another problem space. And it So, it's great at recognizing things that it's familiar with and things it's seen before, but it's not that

**[1:00]** aren't great in adapting to unfamiliar environments when there happens to be new date- new data. And so, unlike AI, humans actually excel in this area as you probably know. So, even without a clear reward signal, we're able to learn flexibly and adapt to new rules that we learn. And we call this sparse reward learning. And so, to study this, I built a benchmark puzzle-based benchmark that's currently unsolvable by AI. And so, I'm going to show you a quick

**[1:30]** clip of that with my lovely, volunteer, Miles, who filmed for this. And, I want to preface this by saying that Miles did not receive any instructions, and he has never seen the puzzle before. How do I do this? Can you hear this? Wait. I don't think my sound's on. Eek. Hold on, sorry. Sorry, 1 second. I am, technologically inept. How do I

**[2:00]** Hey How do I turn the-? Oh, my gosh. Sorry. I think you have to connect to them. What do you call them? Then go to the I mean, we can try maybe Okay, so I see three boxes on the screen: a blue box, a gray box, and the outline of that same blue. I'm just going to move the right arrow key and see what happens. Doesn't do anything. I'll move to the

**[2:30]** Left arrow key, also does nothing. The down arrow key, ah, I'm able to move down. This blue box, it seems to be my character. I can move in this one dimension, but I can't move to the right. If I go down to this gray, okay so two new things have popped up, these outline boxes. And it seems like this gray box is triggering their appearance and disappearance. If I move up to the, so let's see what happens. I'm now able to move oh, I went back into

**[3:00]** so I'm back in this sort of single dimension. So these dotted boxes seem to change the dimension in which I'm able to move in. So, oh yeah, so now I can move up, down, on the right side. Okay, so I took the solid box, now into the outline box, and it seems like that's how I'm able to win the game. That doesn't quite work here. Let's see what happens if I interact with this light gray box. So, I've created a new dotted box. Oh, and this dotted box has changed my color.

**[3:30]** So I'm assuming that I need to match the colour to win the game. Yes, okay. Great. So here, am I, okay, so I'm this yellow box at the moment, so I need to somehow make it to this red box, and also be red to win the game. I'm assuming that's how this is going to go. So this is not changing my colour this time. Oh yes, so I'm restrict, so I have

**[4:00]** Instead

**[4:30]** I can move so that's changed my color so I'm assuming I need to rearrange these dotted boxes here by going to the gray box to see if I can make it to the sort of like lime green box. So I'll change my color to match the green and then I'll go into this dimension changing box. Great. Okay. This seems to be the pattern here. How does

**[5:00]** Okay, a quite a few more of these dotted boxes here. This is a dimension changing box, I know that. I didn't quite get with that one was, but Okay, spoiler alert, Miles solves the puzzle to completion. I'm going to keep going I mean there's not much time left, but Ooh. My gosh, sorry. My presenter notes disappeared.

**[5:30]** Ay. Sorry. Oh, my gosh. Ay, ay, ay, ay. Presenter view. Everything is going smoothly and you cannot see this. Presenter view. Okay. Oh, thank God. Oh, you're not supposed to see that. Okay.

**[6:00]** Wait. My gosh, it's backwards. What do you need to do? It's just it's so confusing because it's backwards. I like I want it to be full screen, this one. Yeah, wait. Damn, all my times- Oh, you paused it. Thank you so much. Yeah. He took pity on me. You want the notes? I th- just want the notes on my computer, Yeah. which is what I had before, but I didn't have the sound on.

**[6:30]** And then I think we should Do you need the notes? Yeah, but like on my computer. So, ugh, why is it doing that? Just skip it, alright? Let's skip it. Yeah, I think we probably won't, right? Ugh, I mean, okay. I would have liked to use them, but it's fine. Okay. You got this. Thank you. Oh my god. Anxiety sweating. Anyways, so lessons learned, from this

**[7:00]** environment in this really interesting way. I wanted to think about how AI learns, and I'm sure that you're familiar with the exploration exploitation trade-off that powers how we now have reinforcement learning today. But I ran a user study with 75 participants who played my benchmarks, just like Miles did, to completion, and I found that humans are actually solving it with this third mechanism that occurs in between exploration exploitation, which I'm calling establish. So establish is an in-

**[7:30]** intermediary hypothesis testing mechanism that you learn to test, revise, and confirm different rules that and parts of the environment that you learn through exploration exploratory driven learning. So, this is what it looks like in a model. It's called the Triple E Model. So, how Miles was going through that was he was you might have said, "Oh, I think this is happening. I wonder if this thing's happening and oh, actually

**[8:00]** the color changed, or, "Oh, I didn't expect that." and I've noticed that in all my participants, there is this, like I said, this intermediary component where you're operating under partially known info, information, or in machine learning, what we would call a partial world model. In formal methods, you would call this a specification, you're and when you have completed this model, it would be a specification that you've learned about this state space or environment. And so, what

**[8:30]** human cognition offers us that symbolic approaches, such as state machines, or, DFAs, also offer us, that neural approaches, like LLMs, don't offer us, are interpretability and more efficiency with learning from our data. And so, ooh. And, this is really important because if we want to build more flexible, better AI, we're going to have to learn from human cognition, which, as I'm sure you can guess,

**[9:00]** is a little overlooked in machine learning and computer science in general. So, but by learning from this, we'll be able to build stronger, better, more reliable AI that is able to be more flexible in new environments when it interacts with new information. And so kind of the thesis, the main premise is that humans teach us this, these principles that will be have implications for actual architectures we build, architectures with

**[9:30]** Hypothesis testing mechanisms, for example. And yeah, honestly that's pretty much it. I have like a minute left, but I had more to say, and I forgot. So, sorry. That was it. Oh, yeah. Also, like, sorry. I totally forgot my notes. If you have actual, like, research questions, happy to talk about this afterwards.

**[10:00]** I just kind of blacked out seeing all of you, so. That's for sure. Thank you.
