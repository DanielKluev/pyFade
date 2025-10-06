# Interactive Beam Search

## Intro

Interactive beam search is interactive version of beam search algorithm. 
Classic beam search iteratively beams out at specific positions, then prunes least preferred beams, until final completion is formed.
Interactive beam search allows user to guide the beam search process, by choosing at which positions to beam out, and which beams to keep or prune.

This process allows to discover suppressed or low-probability completions which are still within model's latent manifolds, but are not reachable via classic sampling or generation methods.

### TBD