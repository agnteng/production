Title: AI Agent Books a Table by Phone: ElevenLabs + Twilio - Sebastien Couture

Sebastien Couture gives a live demo of a phone-call skill making a restaurant reservation.

Main Takeaways

- Architecture: main agent → "make phone calls" skill → call subservice (ElevenLabs + Twilio) with a scoped prompt.
- Cost: less than 20¢ per call. Twilio is the expensive piece at ~7¢/min.
- Privacy by partitioning: the call subservice runs in a separate process which sends only the information relevant to the call to ElevenLabs.
- The system self-improves with edge cases surface in transcripts, the main agent updates the call rules.

Sebastien Couture
X: https://x.com/seb3point0
LinkedIn: https://www.linkedin.com/in/couturesebastien/
GitHub: https://github.com/seb3point0
