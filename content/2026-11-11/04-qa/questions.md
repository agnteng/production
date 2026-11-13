## Q&A

After the third talk, Andy, David and Sacha took questions together. These are
condensed from the recording.

---

#### How often do you write ADRs, and are they for design or technical decisions?

**David Mihal:** About one a day. Almost all of them are technical
architecture decisions: the codebase is mostly backend Rust, and the frontend
is a minor part. He rarely decides himself any more. The agent proposes one
("want me to make an ADR for this before we start?") or ships one alongside a
PR. Now and then it writes one that didn't need to exist.

#### Don't ADRs blow up context and token spend?

**David Mihal:** He hasn't hit it. He expects ADRs to save context, because a
short text file is cheap compared with the agent scanning long code files to
reconstruct why something is the way it is. He hasn't measured it.

#### Does the agent eventually learn your tribal knowledge, so you need fewer ADRs?

**David Mihal:** No, they haven't written fewer, just different ones. Early
on the codebase was small and so were the decisions. ADRs also sit beside many
other markdown files (specifications and descriptions) that keep being updated.

#### Are ADRs portable across projects?

**David Mihal:** Not really. They're specific to that codebase, which is
mostly one monorepo. At most, an agent could summarise them as context for
something else. For this talk he had Claude go through all his ADRs to pick
examples.

#### Have you looked at Kiro?

**Andy Nikulin:** He'd call Kiro an ADE more than a harness, and he likes it.
For a long time Kiro let you register as many accounts as you liked and loop
through them without paying, "which I did back in the day." On token pricing he
couldn't say: they still charge you, and comparing prices wasn't the point of
his talk. "Whoever didn't try Kiro, try that."

#### What's the cheapest way to get Opus outside Anthropic?

**Andy Nikulin:** The one on his slides, cheaperinference.com, which he isn't
affiliated with. It's fairly safe with your money, stable, and 30–55% off. He
uses it himself.

#### Can you treat accounts as throwaway and keep your work safe?

**Andy Nikulin:** His whole scenario is API use, and the API keeps no memory:
every call starts from zero. Swapping accounts behind a web or agent interface
is a different problem, and he couldn't say. An audience member added that
each new account needs a new phone number. Swappable-number services exist, but
only some numbers are accepted.

#### How do you balance shipping with keeping up with new tools and models?

**Andy Nikulin:** "Another sleepless night." He jumps in when something new
appears. New models reach the token stations within a week or ten days, so
there's time to prepare. And there's no vendor lock-in: point the harness at
model A, B or C at about the same price and compare the results.

**Sacha Dumay:** He listens as little as possible and filters the noise. If a
model or tool still reaches him from friends after a few weeks, he tries it on
his own work, Claude Code for example, never on the production pipeline. Every
question the agent got wrong goes into the evals. A new model ships only if it
scores at least as well.

**David Mihal:** "The best way to learn about new stuff happening in AI is to
come to your local AI meetup." Beyond that, podcasts and friends. He admits he
doesn't get enough time to try things. His team keeps meaning to set time
aside, but it's hard to break the cycle when the next feature is waiting.

#### "Never use workflows": even for users who don't know where to start?

**Sacha Dumay:** It's a work in progress. A workflow is fine as an MVP, while
you don't know yet what you want. Past that you end up with 10, 20, 100 of them
and stop maintaining them. One or two agents with tools are easier to maintain.
Workflows are also brittle: a task one degree off breaks them, "even if you put
some LLM in it."

#### How would eve make a chatbot SaaS actually agentic?

**Sacha Dumay:** In a way, yes. eve gives you a framework for the big pieces
Claude Code has: tools, memory, scheduler, sandbox and so on. You may not need
all eight, but they're there when you do, and you can start with one. It's open
source, so you aren't locked in to OpenAI or anyone else.

#### How do you limit what the agent can touch?

**Sacha Dumay:** Vercel supplies many of the pieces, including the sandbox.
For connectors you build nothing: you pick GitHub or Linear in Vercel, paste an
API key, and they manage it.

#### Where do you draw the line between deterministic code and agent skills?

**Sacha Dumay:** Two things. User approvals must be deterministic. And so must
anything that's the source of truth: their repo has an accounting folder that's
"red, no-touch AI." Ledger writes go through tools that are deterministic code
underneath. The LLM never writes SQL on the fly.

#### And security beyond the database, like the agent reaching your private network?

**Sacha Dumay:** It's scary. What reassures him is that models hallucinate far
less than six months ago: still not deterministic, but much more reliable. You
still don't open everything up at once. It's a product judgement. For
Cashflowy the red line is the accounting layer; for someone else it might be
unrestricted web browsing.

#### How much does eve lock you in to Vercel?

**Sacha Dumay:** It's fully open source, so yes. The chat runs on what Vercel
calls workflow, a background-job layer similar to Inngest (which he still uses
for many background tasks), and they nudge you towards it. He hasn't adopted
their sandbox yet. Out of the eight or nine components, maybe 10% is lock-in,
and it's easy to swap out. "Low lock-in, but they make it easy for you to stay
in Vercel."

#### How do you stop markdown docs rotting over time?

**David Mihal:** ADRs rot less because they're static once written. The other
markdown does drift, because agents edit iteratively and one section keeps
growing. He keeps a list of "evergreen" jobs for spare tokens at the end of the
week on his Claude plan. One is "look over the documentation and find areas that
could be organised or cleaned up."

#### Why not keep ADRs outside the codebase, in Linear for example?

**David Mihal:** It could make sense. They use Linear too, at about one ADR a
day against 20 or 30 Linear tickets, and Linear also runs their support. ADRs
fit the codebase because most work happens in one monorepo. A multi-repo setup
might want them centralised. They also have a shared Obsidian vault his agent
can read, plus GitHub, and he hasn't found a good way to tie all that context
together. "Maybe there's a product there, like an ADR MCP server."
