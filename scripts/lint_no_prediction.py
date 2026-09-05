#!/usr/bin/env python3
"""Ban invented numbers and prediction vocabulary from anything a reader sees.

There is no data behind "45-65% chance of an interview"; it is a made-up number that
reads with the authority of arithmetic. The ban is on the CONCEPT, not on the
punctuation: `匹配度 85 分` and `rated 8.5` are the same invented number as `85%`,
and for two years this file caught only the ones carrying a `%` or a slash. Collapsing strong / partial / gap into one
score needs a weight for a partial match, and any weight would be invented too. So the
conclusion is a word, the counts are printed with the evidence behind each row, and
this lint keeps the made-up numbers out.

Five things are masked before any scan, and every one of them was a live false
positive on output this skill's own files mandate:

* The verdict labels. 大概率被筛掉 -- the human-facing label for likely_screen_out --
  literally contains 概率. Without masking, this lint fires on the most common verdict
  the skill prints, and a gate that cries wolf on ordinary output is one people switch
  off. A bare 大概率 elsewhere still fires. The labels come from scripts/vocab.py and
  are never re-typed here: a hand-copied second spelling would silently un-mask the
  verdict it was copied from.
* URLs. https://www.gov.uk/2026/08/09/x matches the n/m score pattern and %20 matches
  the percent ban. A URL is an identifier, not a claim -- the same reason a citation's
  title is exempt from the digit ban in the market tables.
* The 30/60/90 planning horizon. modes/assess.md §10 REQUIRES a 30/60/90 table on
  exactly the two verdicts where the "what to do instead" half is the whole value, and
  _SCORE matches the 30/60 inside it. One token is masked; 8/11 still fires.
* The payload of a `quote=` field, inside a MOCK-*-V1 block only. An interview
  transcript is the one place in this skill where a number a HUMAN said out loud is the
  evidence, and "roughly 40% faster" is exactly the over-claim the provenance assessor
  is there to tag. Failing the file would force the transcript to be laundered, which
  deletes the finding and keeps the file. The assessor's own prose on the same line,
  and every line outside the block, is scanned as usual.

* Numbers this round CAPTURED, quoted with their neighbouring words. An employer's
  own job title can contain a percentage -- `AI/ML Engineer (100 % remote)` is a real
  LinkedIn card -- and discover renders titles exactly as captured. With no exemption
  the two rules contradict each other and the artifact that fails is the honest one.
  This masking differs from the four above in kind: it is not a list somebody
  maintains, it is a lookup against what the adapters and the fetcher actually
  returned, so it cannot go stale and cannot be widened by editing this file.

The one allowlist: where an employer publishes its own rubric, the skill may walk the
candidate through THAT scale, in the employer's wording, with the source named. Quoting
an employer's scale is reporting. Treating it as a conclusion is inventing.

Exit 2 still writes a receipt, verdict "could_not_run", unless the workspace directory
itself is absent -- there is nothing to append to.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import journal  # noqa: E402
import vocab  # noqa: E402

GATE = "lint_no_prediction"

# Derived, never re-typed. The zh labels and the banned-word list are two views of
# the same closed set -- 大概率被筛掉 contains 概率 -- so a second hand-written copy
# here would un-mask whichever label drifted. Longest first, so masking a short
# label can never leave the tail of a longer one behind.
VERDICT_LABELS = tuple(sorted(
    tuple(vocab.VERDICT_ZH.values()) + tuple(vocab.VERDICTS) + (vocab.REFUSAL,),
    key=len, reverse=True))

_URL = re.compile(r"https?://\S+")
# A planning horizon, not a score. modes/assess.md §10 mandates the table.
ROADMAP_HORIZON = re.compile(r"(?<![0-9])30\s*/\s*60\s*/\s*90(?![0-9])")
_MOCK_OPEN = re.compile(r"^\s*MOCK-[A-Z]+-V1\s*$")
_MOCK_CLOSE = re.compile(r"^\s*END-MOCK-[A-Z]+-V1\s*$")
_QUOTE_FIELD = re.compile(r"quote=")
# Fullwidth forms are the same claim in the same language. `％` (U+FF05) and `／`
# (U+FF0F) are what a Chinese IME produces by default, and `０-９` likewise — so
# the ASCII-only classes these replace left the ban unenforced in exactly the
# text it was most needed in.
#
# NOT solved by NFKC-normalising the line first, which is the obvious fix and the
# wrong one: `mask_exempt_spans` blanks URLs and verdict labels by replacing them
# with runs of spaces OF THE SAME LENGTH so the reported span still lines up with
# the original text. NFKC changes lengths (`％`→`%` is 1:1, but `㍑`→`リットル`
# is not), and a normalising pass would silently break that alignment. Widening
# the character classes keeps every offset exactly where it was.
# `‰` and the abbreviation `pct` are the same claim in different clothes;
# both exited 0.
_PERCENT = re.compile(r"[%％‰]|(?<![A-Za-z])pct(?![A-Za-z])", re.I)
_SCORE = re.compile(r"(?<![0-9０-９])[0-9０-９]+\s*[/／]\s*[0-9０-９]+(?![0-9０-９])")

# The Chinese half was four hand-listed words, so 「成功率」「入围率」「七成」 and
# 「百分之七十」 all shipped clean — and `--lang zh` is the DEFAULT
# (count_coverage.py:170), which made this the skill's primary output language.
#
# A bare `X率` would be wrong in the other direction: 效率, 利率, 增长率 and
# 采样率 are ordinary words on an engineer's CV. The character class is bounded
# to the words that describe getting the job, so it cannot reach them.
#
# 可能性 is deliberately ABSENT. The mandated disclaimer is
# 「本 skill 不给出面试或录用的可能性估计」 — banning the word would make the
# required text fail its own gate, which is the defect layer 1 already had once.
# Spelled out, not a character class. `[通过入围命中录取用成功面试中签]{1,3}率`
# matched any 1-3 of those characters before 率, so it fired inside ordinary
# business words the skill's own market cards use: 达成率 ("成率"), 交付率,
# 出勤率. A ban that fires on honest, mandated content is a ban that gets
# switched off. These are the words that describe GETTING THE JOB, and
# nothing else.
_ZH_RATE = ("概率|通过率|命中率|录取率|录用率|成功率|入围率|中签率|面试率|"
            "机率|機率|錄取率|錄用率|成功機會|勝算")
# 七成 = 70%. The lookahead keeps 成功/成长/成员/成果/成本/成熟/成为 out; those are
# the ordinary compounds a Chinese numeral can legitimately sit in front of.
# Arabic digits too. `八成` fired and `8 成` did not — a pre-existing gap this
# audit walked into, and the two spellings are the same claim.
_ZH_TENTHS = r"[一二三四五六七八九0-9０-９]\s*成(?![功长员果本熟为立就分交交])"
_ZH_PERCENT_SPELLED = r"百分之[零一二三四五六七八九十百]+"
# Japanese tenths. `_ZH_TENTHS` gave Chinese 七成 its own rule and Japanese has
# the exact parallel in 割 — `可能性は7割です` is the same invented probability
# and sailed through a file whose commit claimed every language it writes in.
_JA_TENTHS = r"[0-9０-９一二三四五六七八九][\s]*割(?![引り])"

# Outcome forecasts in the other languages this skill writes in. The English and
# Chinese vocabularies were enforced and the rest were not, so
# `Sie werden das Vorstellungsgespräch sicher bekommen.`,
# `Je hebt een grote kans op een gesprek.`, `面接に呼ばれる可能性が高いです。` and
# `합격 확률은 높습니다.` all shipped while their English twin fired.
#
# Kept to the NOUN of chance and to a modal aimed at an interview or an offer,
# for the same reason the English set is: this must not fire on an honest
# sentence about the job itself.
# `Chance` and `kans` are the ORDINARY words for "opportunity" in German and
# Dutch — `Chancen zur Weiterbildung`, `kansen voor groei` are what postings
# actually say — so banning them bare cried wolf on honest text. English keeps
# its bare `chances?` because "chance" rarely carries that sense there; the
# collision rate is a fact about the language, not an inconsistency.
#
# So they fire only next to an OUTCOME, or in the idiom that is a forecast on
# its own. `Wahrscheinlichkeit` and `waarschijnlijkheid` stay bare: those mean
# probability and nothing else.
# Proximity to a JOB NOUN was the wrong test and an independent pass proved it:
# `die Chance, in diesem Job viel zu lernen`, `de kans om veel te leren in deze
# baan` — job nouns are exactly what makes OPPORTUNITY language job-related, so
# that rule fired on 6 of 6 honest recruiting sentences.
#
# A LIKELIHOOD predicate is the real separator. `Die Chancen stehen gut` and
# `een grote kans op een gesprek` say how probable; `wir bieten die Chance` and
# `grijp de kans` say what is on offer. `gut`/`goed` are deliberately NOT in the
# list — `eine gute Chance, das Team kennenzulernen` is an offer, and including
# them puts the false positive straight back.
_DE_LIKELIHOOD = r"hoch|gering|gro\u00df|klein|niedrig|steh(?:en|t)|liegt bei|betr\u00e4gt"
_NL_LIKELIHOOD = r"groot|grote|klein|kleine|hoog|hoge|laag|lage|gering"
_FORECAST_DE = (r"\bwahrscheinlichkeit\b"
                r"|\b(?:chance|chancen|aussichten)\b[^.!?]{0,40}\b(?:" + _DE_LIKELIHOOD + r")\b"
                r"|\b(?:" + _DE_LIKELIHOOD + r")\b[^.!?]{0,25}\b(?:chance|chancen|aussichten)\b"
                r"|\bwerden\b[^.!?]{0,40}\b(?:einladung|vorstellungsgespr\u00e4ch|"
                r"zusage|angebot)\b[^.!?]{0,20}\b(?:bekommen|erhalten)\b")
_FORECAST_NL = (r"\bwaarschijnlijkheid\b"
                r"|\b(?:kans|kansen)\b[^.!?]{0,40}\b(?:" + _NL_LIKELIHOOD + r")\b"
                r"|\b(?:" + _NL_LIKELIHOOD + r")\b[^.!?]{0,25}\b(?:kans|kansen)\b"
                r"|\bkrijgt\b[^.!?]{0,40}\b(?:gesprek|uitnodiging|aanbod)\b")
_FORECAST_FR = (r"\b(?:probabilité|probabilités|chances? d[eu']"
                r"(?:\s|’)?(?:être|obtenir|décrocher))\b")
_FORECAST_ES_IT = (r"\b(?:probabilidad|probabilidades|probabilità)\b")
_FORECAST_JA = r"可能性が高い|見込みが高い|確率|受かる見込み|通る見込み"
_FORECAST_KO = r"확률|가능성이 (?:높|큽)|합격할 것"

_WORDS = re.compile(
    # `chances?` used to be bare. That was tolerable while this file only ever
    # read English — and it stopped being tolerable when the skill started
    # writing German assessments, because `Chance` is spelled identically and
    # this pattern is case-insensitive. `Wir bieten dir die Chance, in diesem
    # Job viel zu lernen` fired as an English prediction word. So did every
    # honest English `a chance to work with…`.
    #
    # It now needs a possessive or an outcome, which is what makes it a claim
    # about THIS candidate rather than a word for opportunity in either language.
    r"\b(?:your|their|his|her|our|my|the candidate'?s?)\s+chances?\b"
    r"|\bchances?\s+(?:of|at|for)\s+(?:an?\s+|the\s+)?"
    r"(?:interview|offer|job|role|position|success|being|getting|landing|"
    r"a\s+callback|progressing)"
    r"|\bchances?\s+(?:are|is|were|seem|look|looked)\b"
    r"|\bprobabilit(?:y|ies)\b|\bodds\b|\blikelihood\b"
    r"|\blikely to be (?:hired|interviewed|shortlisted|rejected)\b"
    r"|\b(?:strong|weak) candidate\b|\bwould pass\b|\bno-hire\b"
    r"|\b\d+(?:\.\d+)?\s*(?:percent|per cent)\b"
    r"|\bout of (?:10|100)\b"
    # Forecasts that name no number. The ban is on PREDICTING the outcome, and a
    # verification pass found the numberless English forms sailing through while
    # their Chinese analogues fired — the gate enforced in one language only.
    r"|\bshoo-?in\b|\ba lock\b|\bin the bag\b"
    r"|(?:\b(?:will|would|should)\b|'ll|’ll)\s*(?:almost certainly\s+|certainly\s+|surely\s+|"
    r"probably\s+|likely\s+)?(?:get|land|receive|secure)\s+(?:an?\s+|the\s+)?"
    r"(?:interview|offer|job|role|position)\b"
    r"|\bexpect\s+(?:an?\s+|the\s+)?(?:interview|offer)\b"
    r"|\byou'?re? (?:a )?(?:strong|weak|clear|obvious) (?:fit|match|candidate)\b"
    # 確率 is the Japanese/traditional spelling of 概率.
    r"|確率"
    r"|" + _ZH_RATE + r"|" + _ZH_TENTHS + r"|" + _ZH_PERCENT_SPELLED
    + r"|" + _FORECAST_DE + r"|" + _FORECAST_NL + r"|" + _FORECAST_FR
    + r"|" + _FORECAST_ES_IT + r"|" + _FORECAST_JA + r"|" + _FORECAST_KO
    + r"|" + _JA_TENTHS,
    re.IGNORECASE)
_ATTRIBUTION = re.compile(r"^\s*>?\s*(?:—|--|-|Source:|来源[:：])\s+.*https?://\S+")


# ---------------------------------------------------------------------------
# Score NOUNS. The two bans above catch the SYMBOLS -- `%` and `n/m` -- and an
# audit on 2026-09-05 measured what that leaves through, on the invariant this
# whole file exists for: `匹配度 85 分`, `overall score: 85`, `rated 8.5`,
# `4.5 stars`, `confidence: 0.85`, `grade: B+`, `Bewertung 8` all shipped
# silently. Collapsing evidence into a number needs a weight for a partial match
# and any weight would be invented -- that is true whichever word carries the
# number, so the ban has to be on the concept and not on the punctuation.
#
# Covering the languages this skill renders CVs in (en/de/nl/fr/es/it/zh/ja/ko),
# because banning it in English and Chinese only is the defect one level up.
#
# NOT included, deliberately: a bare `85 points`. `points` is ordinary prose --
# references/motivation-letter.md really does say "3 points" -- and this repo
# treats a gate that fires on correct output as the worse failure. A stated hole
# beats a cry-wolf.
_SCORE_NOUN_LATIN = (r"scores?|scored|scoring|ratings?|rated|graded|"
                     r"bewertung|punktzahl|beoordeling|cijfer|"
                     r"puntuaci[o\u00f3]n|punteggio|valutazione")
# `note` (fr) and `mark` (en) are left out on purpose: both are high-frequency
# ordinary words, and a French grade written `15/20` is already _SCORE's.
_SCORE_NOUN_CJK = (r"匹配度|契合度|吻合度|评分|評分|打分|得分|分数|分數|总分|總分|"
                   r"综合分|綜合分|评级|評級|等级|等級|評価|点数|點數|점수|평점|평가")

# WHERE each half applies. D2 bans the skill from scoring THIS CANDIDATE'S FIT;
# it does not ban the candidate's own past, measured results — which is exactly
# why cv.md and letter.md were excluded from this lint from the start.
#
# `mock/cheatsheet.md` and `mock/answer-guide.md` are the same kind of file: the
# candidate's own material, to be said out loud. A cheatsheet reminding someone
# they "scored 92 on the HackerRank test last year" or that a repo "received 500
# stars" is honest sourced history, and banning it there was a cry-wolf found on
# 2026-09-05. The judgement-facing artifacts — where the skill itself writes the
# number — keep the full ban.
#
# The FIT nouns stay banned everywhere, including on the candidate's own pages:
# 匹配度/契合度 and `fit score`/`match score`/`confidence` are about this
# application and can only be invented, wherever they are written.
_JUDGEMENT_SURFACES = ("fit-assessment.md", "shortlist.md", "assessment-")
_FIT_NOUN = re.compile(
    r"(?:匹配度|契合度|吻合度)\s*[:：为是]?\s*"
    r"(?<![0-9０-９.．\-\u2013])[0-9０-９]+(?:[.．][0-9０-９]+)?"
    r"|\b(?:fit|match|compatibility)\s+(?:score|rating)\b\s*(?:of|:|=|is)?\s*"
    r"(?<![0-9.\-\u2013])[0-9]+(?:\.[0-9]+)?\b",
    re.I)


def _is_judgement_surface(label: str) -> bool:
    name = str(label or "").replace("\\", "/").split("/")[-1]
    return any(mark in name for mark in _JUDGEMENT_SURFACES)


_SCORE_NOUN = re.compile(
    r"\b(?:" + _SCORE_NOUN_LATIN + r")\b\s*(?:of|:|=|is|at|von|van|di)?\s*"
    r"(?<![0-9.\-\u2013])[0-9]+(?:\.[0-9]+)?\b(?![/／])"
    r"|(?:" + _SCORE_NOUN_CJK + r")\s*[:：为是]?\s*"
    r"(?<![0-9０-９.．\-\u2013])[0-9０-９]+(?:[.．][0-9０-９]+)?(?![/／])",
    re.I)
# The `(?![/／])` tail hands `score 8/11` back to _SCORE, which already owns the
# n/m shape. One defect, one finding: reporting the same span twice is how a
# reader learns to skim the finding list.

# A confidence expressed as a fraction of one is the same claim wearing a decimal.
_SCORE_DECIMAL = re.compile(
    r"\b(?:score|rating|fit|match|confidence|probability)\b\s*(?:of|:|=|is)?\s*"
    r"0?\.[0-9]+\b", re.I)

# Units that ARE a scale on their own.
_SCORE_UNITS = re.compile(r"\b[0-9]+(?:\.[0-9]+)?\s*(?:stars?|pts)\b", re.I)

# Letter scales. SKILL.md names `B+` in the same breath as `7/10` and "score: 82".
# The noun is required so an ordinary capital letter cannot trip it.
_SCORE_LETTER = re.compile(
    r"(?:\bgrade\b|\brating\b|评级|評級|等级|等級)\s*[:：=]?\s*"
    r"[A-F][+\-]?(?![A-Za-z0-9])", re.I)

# The bare unit form: 85 分 / 85점. The exclusion lists are what keep this off
# ordinary Chinese -- 分钟, 分析, 分类, 分级 ... and Korean 점심 (lunch). 点 is
# NOT given a bare form: 下午 3 点 is a clock time, so Japanese 点数 has to carry
# its noun above.
_SCORE_BARE = re.compile(
    r"(?<![0-9０-９.．\-\u2013])[0-9０-９]+(?:[.．][0-9０-９]+)?"
    r"\s*(?:分(?![钟鐘析部类類布支别別配享散开開成级級秒钱錢手"
    r"公司行店销銷工区區层層队隊会會段期割母子])|점(?!심))")


# Everywhere this lint runs.
CHECKS = (("PERCENT", _PERCENT), ("SCORE_PATTERN", _SCORE),
          ("PREDICTION_WORD", _WORDS),
          ("SCORE_NOUN", _FIT_NOUN))
# Only where the skill itself is producing the number. See _JUDGEMENT_SURFACES.
JUDGEMENT_CHECKS = (("SCORE_NOUN", _SCORE_NOUN), ("SCORE_NOUN", _SCORE_DECIMAL),
                    ("SCORE_NOUN", _SCORE_UNITS), ("SCORE_NOUN", _SCORE_LETTER),
                    ("SCORE_NOUN", _SCORE_BARE))


_WS = re.compile(r"\s+")
# Only tokens that could carry an invented NUMBER are eligible for the capture
# masking. A prediction WORD that happens to sit in the posting is still the
# model's to justify -- verbatim quotation has the blockquote allowlist for that.
_NUMERIC_TOKEN = re.compile(r"[0-9\uff10-\uff19%\uff05]")


def _normalise(text: str) -> str:
    return _WS.sub(" ", str(text)).casefold()


def _json_strings(node, out: list) -> None:
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            _json_strings(value, out)
    elif isinstance(node, list):
        for value in node:
            _json_strings(value, out)


def journaled_captures(workspace: pathlib.Path) -> list:
    """The raw files an `adapter_call` record names, and nothing else.

    `stdout_file` is stored workspace-relative by the wrapper. A path that escapes
    the workspace is dropped rather than followed: a journal is data, and a data
    file that can name `/etc/passwd` as a capture is a traversal, not a corpus.
    """
    root = workspace.resolve()
    out, seen = [], set()
    for record in journal._records(workspace):
        if record.get("action") != "adapter_call":
            continue
        named = record.get("stdout_file")
        if not named:
            continue
        path = (workspace / str(named)).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.is_file() and path not in seen:
            seen.add(path)
            out.append(path)
    return sorted(out)


def capture_corpus(workspace: pathlib.Path) -> str:
    """Everything this round actually CAPTURED, normalised for membership tests.

    Only true captures go in: `raw/*.json` as written by the adapter wrapper, and
    the fetched `posting-source.txt`. Artifacts the model authors -- shortlist.yaml,
    the rendered markdown -- are deliberately excluded. A corpus the model can write
    is a corpus the model can use to authorise its own invented number, which would
    turn this masking into an off switch.

    A raw file only counts if the journal says an adapter wrote it. Globbing
    `raw/*.json` was an OFF SWITCH, measured: dropping a hand-written
    `{"scratch": "fit score 8/10 overall"}` into that directory took the lint from
    exit 1 to exit 0 on unchanged prose. The corpus has to be what the adapters
    actually returned, and the only record of that is the `adapter_call` line the
    wrapper appends -- which the model cannot write without running the adapter.

    An unreadable capture is skipped rather than fatal: this function only ever
    REMOVES findings, so a corpus that comes back short fails closed.
    """
    pieces: list[str] = []
    source = workspace / "posting-source.txt"
    if source.is_file():
        try:
            pieces.append(source.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    for path in journaled_captures(workspace):
        try:
            node = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        _json_strings(node, pieces)
    # NUL joins the documents so a window cannot match across two of them.
    return _normalise(" \x00 ".join(pieces))


def mask_copied_numbers(line: str, corpus: str) -> str:
    """Blank numeric tokens this round captured verbatim, preserving length.

    The exemption is deliberately narrow: the token carrying the number, plus one
    neighbouring token on each side, must occur CONTIGUOUSLY in the capture. So
    quoting `(100 % remote)` off the card is exempt, while writing `100 % chance`
    around a number the card happened to contain is not -- the neighbours are what
    make it a quotation rather than a reuse of the digits.

    The window matches on TOKEN boundaries, not as a substring. A bare `8/10`
    passed as "captured" because the corpus held
    `https://example.com/2026/08/10/job` and `"8/10" in that` is true -- every
    capture carries dated URLs, so substring matching handed the exemption to any
    n/m a model cared to write. Both sides are space-padded, which is exact
    because `_normalise` has already collapsed all whitespace to single spaces.
    """
    if not corpus:  # fast path only: `x in ""` is already False for every window
        return line
    padded = " " + corpus + " "
    tokens = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\S+", line)]
    out = list(line)
    for index, (start, end, token) in enumerate(tokens):
        if not _NUMERIC_TOKEN.search(token):
            continue
        window = [t[2] for t in tokens[max(0, index - 1):index + 2]]
        if " " + _normalise(" ".join(window)) + " " in padded:
            out[start:end] = " " * (end - start)
    return "".join(out)


def mask_exempt_spans(line: str) -> str:
    """Blank out URLs, verdict labels and the roadmap horizon, preserving length so
    the reported span still lines up with the original text."""
    masked = _URL.sub(lambda m: " " * len(m.group(0)), line)
    masked = ROADMAP_HORIZON.sub(lambda m: " " * len(m.group(0)), masked)
    for label in VERDICT_LABELS:
        if label in masked:
            masked = masked.replace(label, " " * len(label))
    return masked


def mock_block_lines(lines: list[str]) -> set[int]:
    """0-based indices of lines inside a closed MOCK-*-V1 block.

    An unterminated block is NOT exempt. A block that never closes is a malformed
    artifact, and treating it as an exemption would make "type the opening line" a
    way to switch this lint off.
    """
    inside: set[int] = set()
    opened_at: int | None = None
    for index, line in enumerate(lines):
        if opened_at is None:
            if _MOCK_OPEN.match(line):
                opened_at = index
        elif _MOCK_CLOSE.match(line):
            inside.update(range(opened_at, index + 1))
            opened_at = None
    return inside


def mask_mock_quote(line: str) -> str:
    """Blank the payload of a `quote=` field, preserving length.

    `quote=` is last on the line and runs to its end, so everything after it is the
    candidate's own words. Only the payload is masked -- the tag, the ref and any
    prose before `quote=` are scanned exactly as before.
    """
    match = _QUOTE_FIELD.search(line)
    if not match:
        return line
    return line[:match.end()] + " " * len(line[match.end():])


def blockquote_allowlist(lines: list[str]) -> set[int]:
    exempt: set[int] = set()
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith(">"):
            index += 1
            continue
        start = index
        while index < len(lines) and lines[index].lstrip().startswith(">"):
            index += 1
        end = index - 1
        window = [lines[end]] + lines[end + 1:end + 3]
        if any(_ATTRIBUTION.match(candidate) for candidate in window):
            exempt.update(range(start, end + 1))
    return exempt


def scan_text(text: str, label: str, corpus: str = "") -> list[str]:
    checks = CHECKS + (JUDGEMENT_CHECKS if _is_judgement_surface(label) else ())
    lines = text.splitlines()
    exempt = blockquote_allowlist(lines)
    in_mock = mock_block_lines(lines)
    findings: list[str] = []
    for number, line in enumerate(lines):
        if number in exempt:
            continue
        quoted = mask_mock_quote(line) if number in in_mock else line
        masked = mask_exempt_spans(mask_copied_numbers(quoted, corpus))
        for code, pattern in checks:
            for match in pattern.finditer(masked):
                original = line[match.start():match.end()]
                findings.append(f"{code}: {label}:{number + 1}: {original!r} "
                                f"in {line.strip()!r}")
    return findings


def cannot_run(workspace: pathlib.Path, reason: str) -> int:
    """Exactly one receipt on the could-not-run path, then exit 2."""
    print(f"cannot run: {reason}", file=sys.stderr)
    if workspace.is_dir():
        journal.receipt(workspace, GATE, {}, "could_not_run", [f"NO_INPUT: {reason}"])
    return 2


def target_files(workspace: pathlib.Path) -> list[pathlib.Path]:
    found = []
    # mock/answer-guide.md is here because it is the file the candidate reads OUT
    # LOUD in the real room. It shipped unscanned by anything: a "70% chance" line
    # in it passed check_mock and every lint, on the one surface where an invented
    # number is spoken to a human rather than merely printed.
    for relative in ("fit-assessment.md", "shortlist.md", "cheatsheet.md",
                     "mock/cheatsheet.md", "mock/answer-guide.md"):
        path = workspace / relative
        if path.exists():
            found.append(path)
    found += sorted((workspace / "mock").glob("assessment-*.md"))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ban predictions and invented numbers.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--files", nargs="*", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    workspace = args.workspace
    if not workspace.is_dir():
        return cannot_run(workspace, f"workspace {workspace} does not exist")
    files = list(args.files) if args.files else target_files(workspace)
    if not files:
        return cannot_run(workspace,
                          f"no rendered file to scan under {workspace}")

    corpus = capture_corpus(workspace)
    findings: list[str] = []
    hashes: dict[str, str] = {}
    for path in files:
        try:
            relative = str(path.relative_to(workspace))
        except ValueError:
            relative = path.name
        hashes[relative] = journal.sha256_file(path)
        findings += scan_text(path.read_text(encoding="utf-8"), relative, corpus)

    for finding in findings:
        print(finding)
    journal.receipt(workspace, GATE, hashes,
                    "fail" if findings else "pass", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
