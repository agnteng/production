# 0005. Transcription through OpenRouter, default prompt only

- Status: Accepted; amended by 0006 (a local model may time a transcript, never write one) and 0008 (a TTS voice check's comparison transcript)
- Date: 2026-11-13 (moved here from the workspace's org ADR 0004 on 2026-11-14; it binds only this repository)

## Context
Whisper and local speech-to-text are not to be used. On 2026-11-11 a prompt
listing speaker names and product terms made the model invent 1,000+ word
passages, including a whole fake panel; the same audio with the plain prompt
was accurate. Hallucinations cluster in quiet Q&A audio.

## Decision
Audio goes through OpenRouter chat completions with `input_audio`, in
fixed-length chunks whose timing comes from the chunk grid. The prompt is the
plain default; names are fixed afterwards from the slides. When the key
fails, stop and ask; never fall back to another engine. A new model or prompt
is adopted only if it scores at least as well on the transcription benchmark
(`scripts/bench_transcription.py`).

## Consequences
Every chunk is cross-checked against a second pass, and SUSPECT chunks are
re-run at 10 seconds. Model changes need a benchmark run first. Cleanup
happens after transcription, never in the prompt (ADR 0004).
