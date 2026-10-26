"""How long until Claude fetches the right skill: Claude deciding alone vs Jev deciding for it.

Route 1 (claude): Claude sees the mekomil skill in its skill list and the mekomIL tools.
  It decides on its own whether to load mekomil, reads the catalog, picks a skill and
  calls get_skill.
Route 2 (jev): Jev makes three calls (skill needed? -> category -> skill). Claude then gets
  the same question, the same tools and the same system prompt, plus an operator note
  naming the skill to fetch.

The clock stops when Claude starts the get_skill call, or, if it never calls it, when it
starts writing its answer. get_skill itself is not executed. The mekomIL tools are local
stand-ins that return the frozen catalog in data/catalog.

Usage:
  .venv/bin/python run_e2e.py --ids H01,N01,M02 --reps 1   # smoke test
  .venv/bin/python run_e2e.py --reps 3             # all questions, 3 repetitions
"""
import argparse
import csv
import json
import statistics
import time
from pathlib import Path

import anthropic

from run import CLAUDE_PRICE, NONE_TEXT, POLICY, Jev, expected_set, load_data, load_env

ROOT = Path(__file__).parent
DATA = ROOT / 'data'

CLAUDE_MODEL = 'claude-sonnet-5-5'
CLAUDE_EFFORT = 'high'  # the default for Sonnet 5.5, as in claude.ai
MAX_ROUNDS = 8

SKILL_MD = (DATA / 'mekomil-SKILL.md').read_text()
_, FRONT, SKILL_BODY = SKILL_MD.split('---', 2)
MEKOMIL_DESCRIPTION = ' '.join(FRONT.split('description: >-', 1)[1].split())

SYSTEM = f"""You are Claude, an AI assistant. The user is chatting with you.

<available_skills>
<skill>
<name>mekomil</name>
<description>{MEKOMIL_DESCRIPTION}</description>
</skill>
</available_skills>

Skills hold instructions for specific kinds of tasks. When a skill's description matches the
user's request, call load_skill with its name and follow the instructions it returns."""

# Names, descriptions and schemas copied from the mekomIL MCP server (mcp/app/api/mcp/route.ts).
TOOLS = [
    {'name': 'load_skill',
     'description': 'Load the full instructions of a skill from <available_skills> by name.',
     'input_schema': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
    {'name': 'get_catalog',
     'description': (
         'Find a specialist for an Israel-specific question. Return the current category index, '
         'or one category\'s skill list. Call without a category first, then choose 1-2 categories '
         'by what the user is asking about and read only those. Covers Israeli rights, benefits, '
         'tax, municipal charges, housing and urban renewal, war compensation, household budgets, '
         'CVs and employment, local providers, invoicing and Israeli service APIs. '
         'עברית: קטלוג כישורים ישראליים -- מס הכנסה, מע"מ, פנסיה, ביטוח לאומי, מילואים, '
         'זכויות עובדים, שכירות, ארנונה, תמ"א 38 ופינוי-בינוי, פיצויי מלחמה לעסקים, '
         'תקציב משפחתי, קורות חיים, חשבוניות ושירותים דיגיטליים בישראל, בריאות ופיקוד העורף.'),
     'input_schema': {'type': 'object', 'properties': {'category': {
         'type': 'string', 'description': 'Category name, e.g. tax-and-finance. Omit for the index.'}}}},
    {'name': 'list_skill_files',
     'description': (
         "What exists for one skill: SKILL.md, SKILL_HE.md, references/*, scripts/*. "
         "Use before asking for a reference or script by name, with each file's size. "
         "Almost every SKILL_HE.md arrives in several parts; get_skill's reply states how "
         "many, and you must read to the last one. "
         "עברית: אילו קבצים יש לכישור -- הוראות בעברית ובאנגלית, נספחים, וסקריפטים לחישוב."),
     'input_schema': {'type': 'object', 'properties': {'slug': {
         'type': 'string', 'description': 'Skill id, e.g. israeli-pension-advisor'}}, 'required': ['slug']}},
    {'name': 'get_skill',
     'description': (
         'Return one file from one skill, verbatim. Defaults to SKILL.md; pass SKILL_HE.md for '
         'the Hebrew version, which is usually the better file for a Hebrew-speaking user. '
         'When a step asks you to compute or check a threshold and the skill ships a '
         'scripts/ file for it, fetch that script and follow its logic instead of doing the '
         'arithmetic from memory -- the script is where the current rule lives. '
         "Fetch a references/ file only when the step you are on cites it -- never fetch a "
         "skill's whole folder speculatively. "
         'A long file arrives in numbered parts: keep calling with the next part until you '
         'have all of them, because a missing part is missing content, not absent content. '
         'Whatever you load, tell the user which skill you used and credit skills-il through '
         'mekomIL; do not show or invent an upstream retrieval URL. '
         'עברית: מחזיר קובץ מתוך כישור ישראלי -- הוראות, נספח, או סקריפט חישוב.'),
     'input_schema': {'type': 'object', 'properties': {
         'slug': {'type': 'string', 'description': 'Skill id, e.g. israeli-pension-advisor'},
         'file': {'type': 'string', 'description': 'Path within the skill. Default SKILL.md. e.g. references/tax-benefits.md'},
         'part': {'type': 'integer', 'description': 'Which part of a long file to return. Default 1.'}},
         'required': ['slug']}},
]

ROUTED_SKILL = (
    'Routing for this message is already done. A router read the mekomIL catalog and selected the '
    'skills-il skill `{slug}` for this question. Do not call load_skill or get_catalog and do not '
    're-check this choice. Call get_skill with slug `{slug}` now, then answer with it.')
ROUTED_NONE = (
    'Routing for this message is already done: no mekomIL skill is needed. Do not call '
    'load_skill, get_catalog or get_skill. Answer directly.')


def run_tool(name, args):
    """Local stand-ins for the mekomIL tools. Returns (text, is_error)."""
    if name == 'load_skill':
        if args.get('name') == 'mekomil':
            return SKILL_BODY.strip(), False
        return f'Unknown skill "{args.get("name")}".', True
    if name == 'get_catalog':
        path = DATA / 'catalog' / ((args.get('category') or '_index') + '.md')
        if path.parent == DATA / 'catalog' and path.exists():
            return path.read_text(), False
        return json.dumps({'ok': False, 'error': {'code': 'UNKNOWN_CATEGORY'}}), True
    if name == 'list_skill_files':
        return f"{args.get('slug')}\n- SKILL.md\n- SKILL_HE.md  [several parts]", False
    return f'Unknown tool "{name}".', True


class Claude:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def until_decision(self, messages, started):
        """Run the tool loop until Claude starts get_skill or starts answering.
        Returns (decision, ms since `started`, rounds, tool trail, usage totals)."""
        messages = list(messages)
        trail, usage = [], dict(input=0, output=0, cache_read=0, cache_write=0)
        for rounds in range(1, MAX_ROUNDS + 1):
            first_text_at = None
            skill_call_at = None
            with self.client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=16000,
                output_config={'effort': CLAUDE_EFFORT},
                system=[{'type': 'text', 'text': SYSTEM, 'cache_control': {'type': 'ephemeral'}}],
                tools=TOOLS,
                messages=messages,
            ) as stream:
                for event in stream:
                    if event.type == 'content_block_start':
                        block = event.content_block
                        if block.type == 'text' and first_text_at is None:
                            first_text_at = time.perf_counter()
                        if block.type == 'tool_use' and block.name == 'get_skill' and skill_call_at is None:
                            skill_call_at = time.perf_counter()
                response = stream.get_final_message()
            u = response.usage
            usage['input'] += u.input_tokens
            usage['output'] += u.output_tokens
            usage['cache_read'] += u.cache_read_input_tokens or 0
            usage['cache_write'] += u.cache_creation_input_tokens or 0
            calls = [b for b in response.content if b.type == 'tool_use']
            for call in calls:
                arg = call.input.get('category') or call.input.get('slug') or call.input.get('name') or ''
                trail.append(f'{call.name}({arg})')
            skill_calls = [c for c in calls if c.name == 'get_skill']
            if skill_calls:
                return skill_calls[0].input.get('slug', ''), (skill_call_at - started) * 1000, rounds, trail, usage
            if response.stop_reason != 'tool_use':
                at = first_text_at or time.perf_counter()
                return 'NONE', (at - started) * 1000, rounds, trail, usage
            messages.append({'role': 'assistant', 'content': response.content})
            results = []
            for call in calls:
                text, is_error = run_tool(call.name, call.input)
                results.append({'type': 'tool_result', 'tool_use_id': call.id, 'content': text, 'is_error': is_error})
            messages.append({'role': 'user', 'content': results})
        raise RuntimeError(f'no decision after {MAX_ROUNDS} rounds')


def claude_cost(usage):
    return (usage['input'] * CLAUDE_PRICE['input'] + usage['output'] * CLAUDE_PRICE['output']
            + usage['cache_read'] * CLAUDE_PRICE['cache_read']
            + usage['cache_write'] * CLAUDE_PRICE['cache_write']) / 1e6


SECOND_CATEGORY_MIN = 0.10


def jev_route(jev, question, categories, by_category):
    """Three Jev calls: skill needed? -> category -> skill. Returns (slug or NONE, picks, ms, cost).
    Call 1 already decided a skill is needed, so call 3 has no NONE option. When the runner-up
    category gets at least SECOND_CATEGORY_MIN probability, call 3 sees both categories' skills."""
    picks, ms, cost = [], 0.0, 0.0
    need, t, c, _, _ = jev.choose(question,
                                 'Decide whether answering this question needs an Israeli specialist skill.',
                                 dict(SKILL=MEKOMIL_DESCRIPTION, NONE=NONE_TEXT))
    picks.append(need); ms += t; cost += c
    if need == 'NONE':
        return 'NONE', picks, ms, cost
    category, t, c, _, _ = jev.choose(question, 'Choose the one category whose skills best fit the question.',
                                     categories)
    ranked = sorted(jev.last_probabilities.items(), key=lambda kv: -kv[1])
    options = dict(by_category[category])
    if len(ranked) > 1 and ranked[1][1] >= SECOND_CATEGORY_MIN:
        options.update(by_category[ranked[1][0]])
        category += '+' + ranked[1][0]
    picks.append(category); ms += t; cost += c
    skill, t, c, _, _ = jev.choose(question, 'Choose the one skill that best fits the question.', options)
    picks.append(skill); ms += t; cost += c
    return skill, picks, ms, cost


def run_once(route, case, claude, jev, categories, by_category):
    row = dict(jev_picks='', jev_ms=0, jev_cost_usd=0.0, followed_router='')
    started = time.perf_counter()
    messages = [{'role': 'user', 'content': case['query']}]
    if route == 'jev':
        routed, picks, jev_ms, jev_cost = jev_route(jev, case['query'], categories, by_category)
        row.update(jev_picks=' > '.join(picks), jev_ms=round(jev_ms), jev_cost_usd=jev_cost)
        note = ROUTED_NONE if routed == 'NONE' else ROUTED_SKILL.format(slug=routed)
        messages.append({'role': 'system', 'content': note})
    claude_started = time.perf_counter()
    decision, total_ms, rounds, trail, usage = claude.until_decision(messages, started)
    row.update(decision=decision, total_ms=round(total_ms),
               claude_ms=round(total_ms - (claude_started - started) * 1000),
               rounds=rounds, tools=' > '.join(trail), claude_cost_usd=claude_cost(usage),
               claude_tokens_in=usage['input'] + usage['cache_read'] + usage['cache_write'],
               claude_tokens_out=usage['output'])
    if route == 'jev':
        row['followed_router'] = decision == routed and (trail == [] or trail == [f'get_skill({routed})'])
    return row


def summarize(rows):
    print(f"\n{'route':6} {'runs':>5} {'correct':>8} {'median ms':>10} {'claude ms':>10} {'jev ms':>7} "
          f"{'rounds':>7} {'$ total':>9} {'followed':>9} {'errors':>7}")
    for route in ('claude', 'jev'):
        mine = [r for r in rows if r['route'] == route]
        ok = [r for r in mine if not r['error']]
        if not ok:
            continue
        med = lambda k: statistics.median(r[k] for r in ok)
        followed = f"{sum(r['followed_router'] is True for r in ok)}/{len(ok)}" if route == 'jev' else '-'
        cost = sum(r['claude_cost_usd'] + r['jev_cost_usd'] for r in ok)
        print(f"{route:6} {len(mine):>5} {sum(r['correct'] for r in ok):>8} {med('total_ms'):>10.0f} "
              f"{med('claude_ms'):>10.0f} {med('jev_ms'):>7.0f} {statistics.mean(r['rounds'] for r in ok):>7.1f} "
              f"{cost:>9.3f} {followed:>9} {len(mine) - len(ok):>7}")


FIELDS = ['id', 'class', 'rep', 'route', 'query', 'expected', 'decision', 'correct', 'total_ms',
          'jev_ms', 'claude_ms', 'rounds', 'tools', 'jev_picks', 'followed_router',
          'claude_tokens_in', 'claude_tokens_out', 'claude_cost_usd', 'jev_cost_usd', 'error']


def attempt(route, case, rep, claude, jev, categories, by_category):
    row = dict(id=case['id'], **{'class': case['class']}, rep=rep, route=route,
               query=case['query'], expected=case['expected'], decision='', correct=False,
               total_ms=0, jev_ms=0, claude_ms=0, rounds=0, tools='', jev_picks='',
               followed_router='', claude_tokens_in=0, claude_tokens_out=0,
               claude_cost_usd=0.0, jev_cost_usd=0.0, error='')
    try:
        row.update(run_once(route, case, claude, jev, categories, by_category))
        row['correct'] = row['decision'] in expected_set(case['expected'])
    except Exception as error:
        row['error'] = f'{type(error).__name__}: {error}'[:300]
    mark = 'ERR' if row['error'] else ('✓' if row['correct'] else '✗')
    print(f"{case['id']:4} r{rep} {route:6} {mark:3} {row['decision'] or row['error']:40} "
          f"{row['total_ms']:>6} ms  rounds={row['rounds']}  {row['tools']}", flush=True)
    return row


def read_rows(path):
    """Load a results file back with the types summarize() expects."""
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    for r in rows:
        for k in ('rep', 'total_ms', 'jev_ms', 'claude_ms', 'rounds', 'claude_tokens_in', 'claude_tokens_out'):
            r[k] = int(r[k])
        for k in ('claude_cost_usd', 'jev_cost_usd'):
            r[k] = float(r[k])
        r['correct'] = r['correct'] == 'True'
        r['followed_router'] = {'True': True, 'False': False}.get(r['followed_router'], '')
    return rows


def write_rows(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, help='run only the first N questions')
    parser.add_argument('--ids', help='comma-separated question ids, e.g. H01,N01')
    parser.add_argument('--reps', type=int, default=3)
    parser.add_argument('--routes', default='claude,jev', help='which routes to run, e.g. jev')
    parser.add_argument('--out', default='results_e2e.csv')
    parser.add_argument('--retry-errors', action='store_true',
                        help='rerun only the failed rows of --out and replace them in place')
    args = parser.parse_args()

    load_env()
    cases, categories, by_category = load_data()
    claude, jev = Claude(), Jev()
    path = ROOT / args.out

    if args.retry_errors:
        by_id = {c['id']: c for c in cases}
        rows = read_rows(path)
        for i, row in enumerate(rows):
            if row['error']:
                rows[i] = attempt(row['route'], by_id[row['id']], row['rep'], claude, jev, categories, by_category)
                write_rows(path, rows)
        summarize(rows)
        return

    if args.ids:
        cases = [c for c in cases if c['id'] in args.ids.split(',')]
    cases = cases[:args.limit] if args.limit else cases
    rows, n = [], 0
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for rep in range(1, args.reps + 1):
            for case in cases:
                # alternate which route goes first
                order = ['claude', 'jev'] if n % 2 == 0 else ['jev', 'claude']
                n += 1
                for route in [r for r in order if r in args.routes.split(',')]:
                    row = attempt(route, case, rep, claude, jev, categories, by_category)
                    rows.append(row)
                    writer.writerow(row)
                    f.flush()
    summarize(rows)


if __name__ == '__main__':
    main()
