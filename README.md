# The right model for each step

**[Read the results page](https://ilanvys.github.io/jev-mekomil-study/)** (Hebrew and English)

A small experiment on one idea: a task with several steps doesn't have to run entirely on one
large model. Split it, give each step to the kind of model that fits it, and the time to the
answer can drop a lot.

The test case is [mekomIL](https://ilanvys.github.io/mekomil/) (מקומי IL), a skill that lets an
AI assistant load the right Israeli specialist skill from the [skills-il](https://github.com/skills-il)
catalog. Before answering, the assistant has to decide whether a skill is needed and which one.
That step is a decision, not writing, so I gave it to [Jev](https://docs.typesafe.ai), a small
decision model, and measured the time until the right skill is fetched.

## Two routes

- **Route 1, Claude alone (as today):** Claude decides whether a skill is needed, opens the
  mekomIL skill, reads the category index, reads one or two categories, and calls `get_skill`.
- **Route 2, Jev decides and Claude fetches:** Jev makes three short calls (skill needed? which
  category? which skill?). Claude then gets the question plus a note naming the skill, and calls
  `get_skill`.

Both routes use Claude Sonnet 5.5 at high effort, with the same system prompt and tools. The clock
stops when Claude calls `get_skill`, or starts answering when no skill is needed. 53 Hebrew
questions from mekomIL's test set, 3 runs each per route.

## Results

On questions that need a skill (120 runs per route):

| | Route 1: Claude alone | Route 2: Jev + Claude |
|---|---:|---:|
| Median time until `get_skill` | 5.1 s | 1.5 s |
| Claude rounds | 4.1 | 1.0 |
| Right skill fetched | 90% | 92.5% |

Route 2 was faster on all 40 questions that need a skill, and Claude fetched exactly the skill Jev
chose in every run. On 9 of the 13 questions that need no skill it was slower, because there Claude
alone answers right away and Jev only adds time.

**Limits:** only the routing step is measured, not the full answer. 53 questions, and the same
questions were used to develop Jev's routing steps, so the accuracy should be confirmed on new ones.
The mekomIL tools are a local copy of the catalog.

## This is an experiment, not a change to mekomIL

mekomIL is built for everyday, seamless use with Claude or ChatGPT, and aims for a thorough answer
rather than a fast one. It also keeps the user's question private: its MCP server only receives a
category or skill name. Routing through Jev would send every question to another provider first.
The architecture here only demonstrates the point above.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install anthropic
cp .env.example .env                 # add TYPESAFE_API_KEY and ANTHROPIC_API_KEY
.venv/bin/python run_e2e.py --ids H01,N01,M02 --reps 1   # quick test
.venv/bin/python run_e2e.py --reps 3                     # full run → results_e2e.csv
.venv/bin/python report/build.py                         # rebuild docs/index.html
```

## Files

| Path | What it is |
|---|---|
| `run_e2e.py` | The experiment: both routes, the local mekomIL tools, timing |
| `run.py` | Shared helpers (Jev client, data loading) and an earlier, simpler check where both models only picked a skill from a list; its results are in `results.csv` |
| `results_e2e.csv` | One row per run: route, time, rounds, tools called, skill fetched, cost |
| `data/` | Test questions, the skills-il catalog snapshot, and the mekomIL `SKILL.md` |
| `report/` | Page template and build script |
| `docs/index.html` | The results page, served by GitHub Pages |

Costs in the results use list prices, not an actual bill. Not affiliated with TypeSafe, Anthropic,
OpenAI or skills-il. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
