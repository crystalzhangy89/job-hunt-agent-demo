# Job Hunt Agent Demo

A small personal agent that helps with a job search. It compares my resume against job descriptions using the Gemini API, ranks the matches, and keeps a weekly workflow for tracking leads and drafting application material.

## What it does

- **Scores fit**: compares a resume (PDF) with each job description and returns a 0-100 match score, strengths, gaps, and a one-line reason.
- **Keeps rankings current**: only re-scores jobs that are new or changed, and re-scores everything when the resume changes.
- **Reports**: writes a ranked `report.html` and a `results.csv` (opens in Excel).
- **Tracks the weekly routine**: a profile, a repeatable workflow, a leads log, and a reusable prompt keep each week consistent.
- **Handles busy servers**: retries automatically on temporary errors (such as HTTP 503) and falls back to a second model.

## Project structure

```
job-hunt-agent-demo/
├── job_agent.py                  # scores every job in jobs/ against the resume
├── run_agent.bat                 # Windows launcher: scan, then open the report
├── gemini.py                     # quick test of the Gemini connection
├── list_models.py                # list the models your API key can use
├── CLAUDE.md                     # project guide for the AI assistant
├── job_search_profile.md         # target roles, locations, industries, constraints
├── weekly_job_hunt_workflow.md   # the repeatable weekly steps
├── job_leads.md                  # saved leads and notes
├── weekly_run_prompt.md          # the reusable weekly command
└── jobs/                         # one .txt file per job description
```

## Setup

Requires Python 3.9 or newer. No third-party packages are needed.

1. Get a Gemini API key from Google AI Studio.
2. Create a file named `.env` in the project folder containing one line:
   ```
   GEMINI_API_KEY=your_key_here
   ```
3. Put your resume PDF in the project folder.
4. Save each job description as a `.txt` file in `jobs/`.

## Usage

```
python job_agent.py            # score new or changed jobs
python job_agent.py --watch    # rescan every 10 minutes
python job_agent.py --force    # rescore everything
```

Then open `report.html` for the ranked results. On Windows you can also double-click `run_agent.bat`.

## Privacy

This repository should stay private. Never commit `.env`, your resume, or your results. Keep these in `.gitignore`:

```
.env
*.pdf
state.json
results.csv
report.html
job_description.txt
jobs/
```

Your resume and each job description are sent to the Gemini API when you run the scorer.
