# Cited research brief

## Goal

The agent should produce a short, cited research brief on a well-known ML paper, using tools rather than memorized text alone.

## Instruction summary

Ask for a brief on the original Transformer ("Attention Is All You Need"). Require the answer in `/app/answer.txt` with at least one paper URL or DOI and one other `http` citation. The agent should use `paper_search` for the paper lookup.

## Verifier

Binary reward:

- `/app/answer.txt` exists and is longer than 200 characters
- content contains an OpenAlex or DOI URL
- content contains an `http` URL

## Notes

This is a smoke eval for search + citations, not a factuality rubric. Harbor does not read `.env`; pass keys via `--env-file .env` or exported `DEEPINFRA_*` and `TAVILY_API_KEY`.
