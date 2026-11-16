# Me, My Slop, and I

Alex Lajarre. Timestamps are from the start of the clip.
Machine transcript (Gemini via OpenRouter), lightly cleaned and grammar-corrected; names and
products not yet checked against the slides.

**[0:00]** Just need to relax. Okay. Hey, everyone. I'm ready. This talk is going to be about slop. So it's it's title is Me, Myself, and I: Tales of Backpressure. So, I'm Alex Dajar. I'm a contributor a bit of a contributor to π. So, π is a coding agent that you may might have

**[0:30]** heard of. It's used in OpenCL. And I'm also a maintainer of PyVim, which is, an extension that allows you to use Py with a Vim editor, so for those who know, like Vim is a nerdy editor that is, allows you to move around fast through text. So I'll tell you about what happened to me in those, in both of those cases as a contributor and as a maintainer.

**[1:00]** and I am also, I'm going to give you some hints on how to live, slop-free, which is basically like some personal workflows on how to avoid slop. And give a bit of a some ideas, on TUI, so terminal interfaces, because that's that's where we live there, everything's going on in the terminal. Yeah, and so yeah, my extension is the main, theme extension on Zed. It has like a bit more than a thousand downloads a week these days.

**[1:30]** Yeah. So, first story, as a contributor to Pi, real quick, a story that happened to me is that I threw in a pull request, I had a good repro case, I had tests, and it looked good, but it got rejected. So, I want to explain a bit what happened there. It's There are many levels to the to the story, but basically, it ended up with "I'm done with this

**[2:00]** issue and PR, that's from the maintainer of By. So, bad news to me. And maybe I can just switch there and show you, like, what happened which is that yeah, I had this fairly like, well-prepared thing but like this PR that I that I that I threw in was actually generated my by my agents.

**[2:30]** And that happened to me kind of in my back. And I thought, okay, that's fine. I'm just going to write the thing properly and so on, and in the end, it g- it got rejected. So actually, two problems. One is that I can't trust my agent because they are doing things in my back. And two, as the as the maintainer is saying, he doesn't he doesn't, suffer that agents are writing comments. That's another thing, like you don't you don't write comments with your agents when you talk to maintainers. So that that's one

**[3:00]** Listen. And then as a maintainer of PyVim, so there is another that's another story, which is basically someone showed up with a request. So, I- I just like show you the GitHub page, as it's easier. So yeah, so that's going on in Py, and so someone wants to build something fo- so that the extensions as mine, which are

**[3:30]** How extensions to the editor of Pi, right, so it's that's where you type the text can compose with each other. Yeah, there's that's that's the point. It got a bit of follow ship because, as you can see, for example, if you if you look there like a lot of the or the actual Pi extensions, which are editor extensions, ended up complying with this issue. But the thing that I think that that person didn't didn't realize is

**[4:00]** That to implement this with my extension, it required basically 3,000 lines of code. It was far too complex. And, so that that's a I mean, that was from good intentions, and I totally, like, understand why the guy did that. But the problem is that, it sounds Many things sound so easy today that when there are agents, and actually I could produce the code. Like, I could have merged it, but

**[4:30]** did not want to, because it was creating complexity, and then I would have to maintain the complexity. So yeah, Yeah, in short, the agent never says no, so you have to say no. Yeah, and also, as in the in the Pi in the in Pi world everything is an extension, basically. So like, every extension point that you add creates a lot of complexity that you that you have to manage. So that

**[5:00]** so, that's what I was bitten by, I'd say. Yeah, so these were my stories, but it's not, I'm not the only one. So, this is George Hotz saying, in a very recent article, "It is a golden era for buckets and buckets of slop and a dark age for gems of quality." so here I would give some practical recommendations if you want to do, especially if you want to do OSS, like open-source work, and you want to pay attention to quality.

**[5:30]** Not producing slop, and not be confronted by well, not suffer from slop in general. Think about agents as they are producing the code upstream, and you would need to apply back pressure downstream. Cuz that's something that you might have heard, back pressure, so that's that's that's the way I think about it. And the can- kind of the way I'm working on that these days is I'm thinking about an- so the inner le-

**[6:00]** is kind of is me. So it's it's the most costly one, but it's the most robust one let's say. And going to the outer layer like the boundary is basically automated, and you want to push as many of like you want to improve your system so that more and more of the of the of the guards are like the test and like the verification is going outside. So, the in- innermost layer I will give a short demo just after, which is

**[6:30]** like the innermost layer is just the way you work. So you want to you want to apply your judgments. You want to use tools that are easy to make your life to review the code, to write the code. That's what PyCharm is for at the start. I love using as well see mux and hunk. See mux is like a is a terminal and hunk is allowing you to like write and review code, and write comments in code. Then what you want is

**[7:00]** is, repo memory and drift guards. So, like repo is basic repo memory what I mean is anything that is written in markdown files and then it helps you figure out how the repo should work, guidelines. Architecture decision records are really good as well. And drift guards are basically like for example, perf ben- benchmarks. Like as I as I deploy something which is used at each keystroke in Pi, when you use my extension you like each keystroke is going to like trigger the extension, it needs to be very performant, so

**[7:30]** I had these kind of things. And then on the outer layer is a is kind of like, okay, now that I know that my code is good, then how do I make sure that I'm not throwing out like PRs and issues on GitHub you know, in a yolo fashion, which is what happened to me. And so for that I just beat this thing that I called fire-guard-slope which is just

**[8:00]** helping me pass through the bash commands and check when the gh commands are run running, and if it's going to a to a public repo, it's it asks my confirmation. But that's just a special case of a more general thing that you might have heard about, which is kind of, yeah, what I'm calling a credential boundary. So, for example, Paradigm has released Centaur recently, and they are using something like that. It is called iron.s.sh and

**[8:30]** The point is that you ask a proxy to run the thing for you, and the proxy has deterministic rules. So this way, you never you should never you know, produce side effects that you don't want. Yeah, that that's what my agent is telling me to tell you. So, "One PR, one idea. Polish before publish. Write your own replies. Leave a trace of judgment." Okay. Yeah, I just want to finish by a quick

**[9:00]** more basically what I'm using and some thoughts of on how the terminal UIs are working for agents. So, yeah. Some obvious issues are that I mean, the whole thing is like when you use an agent, you use a so REPL is a, you know, where you type something, you hit enter, and it stores the prompts. And but the world is much more complex than that, right?

**[9:30]** So, let me actually just show you the kind of thing I'm doing. Sorry. Yeah, I- I was, yeah. So, here is my, So, th- this is this is like this is me typing stuff there. So, this is like this is just like PyVim so I can just use Vim

**[10:00]** wins, so I can move around? Yeah. That comes up next. Ah, okay. And, yeah, I just wanted to share about this about Hunk on the on the right. And, so, yeah, I can do this right? Okay, cool. So, Hunk is really good because basically you talk to your agent, through comments in the code that happened in another in another pane. So, I just have a s- simple prompt in pi on the left,

**[10:30]** and I tell it to open a tab in Emacs to the right with hunk, and it figures out how to do that, and then I can I can just, and ask it to write comments so I can read through the code without having to like just read every line. I think it's really good. And you can also write like very useful comments like this. Yeah. Yeah, so that that's, I think that's yeah, just a quick remark on like how to make the whole experience a bit better, and I think to just having to type good prompts is

**[11:00]** Not enough. Yeah, that's it. Yeah, this talk was probably more than 70% AI-generated, but yeah. And yeah, these are the tools that I mentioned, so feel free to check them out. Any questions? Yeah. So first of all, thank you so much for your talk. I think it really resonated with the pain that a lot of us are feeling, that like producing code is not

**[11:30]** or the hard part of software engineering, it's actually like landing code on main or publishing, which is a huge bottleneck. And I guess like I see it as an extremist, you know, for the point of the question, there's two different directions that you could take. On your talk, you're like, "Okay, let's have some tools that reduce the amount of crap that other people have to review, or have tools that accelerate reviewing," right? But in this is sort of embedded that there's still going to be a step of review. So the other extreme, right,

**[12:00]** I don't know if you've read this blog article that stipulates that essentially code should just be like compiler output, like it's technically important, but most people in the end ignore it. Like as tools and production become cheaper and better and more efficient, in the end we kind of won't be reviewing so much code as it would be more unfeasible. So, I'm wondering how you think about that paradigm of like should we continue, like how far are you along with developing the tools as a maintainer

**[12:30]** where there's other like bots that are producing code for you to get to review. Like is it working for you? Or how what do you think this acceleration is to you? That in the end we need, I don't know, formal verification or tools that are going to make sure that we don't read code at all. Yeah, so I think I think we still need code because like just like spec driven development kind of kind of stuff right where you just write a markdown spec is just like less

**[13:00]** rigorous than writing code. But like, you probably have like 80% of the code that you're never going to read and that's that's fine. But, there is probably kind of 20% somewhere. And also I think actually George Hotz, he make, he mentions that, I think that's his deeper point in his artic-, his article is that the code that is generated by agents, he, I think he's he's much more stringent than what slop is, like in a sense that I think he would say that much of what I do is slop. For example,

**[13:30]** because actually I realized that much of the code I generate could not be like used as a building block to build something else. And like if you if you expect that level of like composability, which is what you expect from like really good open source projects, then yes, you need to read the code, like, but to some extent again. Like, I think they there are some trade-offs and there are parts that are totally fine. There are parts also that you can like kind of aggressively verify. And those that

**[14:00]** less to read, but architecture you probably need to master still, you know? So, yeah. That's kind of my answer, I guess. Thank you. What was the root cause analysis on how your agent launched the PR without you knowing? Oh, I mean, just try. And you will see it will do it do it for you. I don't know, I'm using GPT 4.5. It does that for me. It does it doesn't even look. It doesn't even ask. It just it just throws the issue and a and a PR.

**[14:30]** Yeah, but I'm, again, I'm using it with pi without safeguards. You know, so it's like in Euro-mode. Probably plays a role. So, I didn't tweak my agents of DMD, and I'm rather like not tweaking too much agents of DMD, and adding deterministic checks. That's kind of the style I try to apply, but then I have failures sometimes. Can we Yeah. Yeah, well, that's like the question that they've had, like of course, that's the core philosophy

**[15:00]** that Mario brings is that Pi doesn't have any safeguards. It's like dangerously skip permissions all the time. How do you, like, protect yourself from it doing something stupid on behalf of you, I don't know, going and destroying a production database or something, or you are, like, not afraid? Yeah, I don't have any production database, for now. I mean, that I'm using these days. I mean, the higher risk for me

**[15:30]** is a file system, a data loss. Yeah yeah, so, like, running a user, a Unix user, that that has, like, only access to some folders, but that's the only thing I do. And actually, I built a whole, like, sandboxed thing. I was thinking about talking about it, but, I am not using it. Because the thing is that every Like, most of the, like, file system stuff, and like commands, like Unix commands, I think the models are really good at, or already

**[16:00]** capturing themselves when it starts getting dangerous. So, I never I never really had a problem. But, like external APIs, this is pure YOLO. So, yeah, I think that I think it comes from RL or something like I never had a problem on Like I never lost data until today apart like from like files in my repo, but that's fine. Like I, you know, I use Git, so like I don't care. The problem the problem is that it can do some it's some operations that you can't undo. For example, it has access to your GitHub API. Yeah. Yeah, yeah.

**[16:30]** It can delete some repository with all like the history, probably. That's not the big problem, but it can— That's— that's why I built this thing for GitHub, because, yeah. So now I have like it's it's prompting me, it's it's asking me for review anytime it does a GitHub operation which is not whitelisted. Yeah. So you're building kind of your harness with these set— Yeah, yeah, because GitHub is like the keys, like the key system in GitHub is not good enough. Otherwise, I could just have used that, but it's it's not so good, so, yeah.

**[17:00]** and how to interact with them. Right, thank you.
