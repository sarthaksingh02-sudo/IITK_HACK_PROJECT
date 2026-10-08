# /data/real/notices/

This folder contains raw government notices copied from official sources.

## Rules
- Every file must have a comment at the top: `SOURCE: <url> | RETRIEVED: <date>`
- Do NOT paraphrase or summarize; paste the original text.
- Filenames: `<type>_<slug>_<YYYYMMDD>.txt`  e.g. `scholarship_obc_postmatric_20261001.txt`
- PDFs are accepted alongside .txt.
- The cloud ingest pipeline (`cloud/ingest.py`) reads these files and sends them to the LLM for structured extraction.

## What to add
Place official government notices here before running `python cloud/ingest.py`.
Example sources:
- https://scholarships.gov.in
- https://sarkariresult.com (verify original source)
- https://upmsp.edu.in
- https://pmkisan.gov.in
- Official employment notification PDFs from SSC, UPSC, state boards.

## Current status
**EMPTY — no real notices loaded yet.**
The cloud seed script (`cloud/seed.py`) will only run if notices are present here,
or if MOCK_LLM=true (for development only — outputs are clearly flagged as mock).
