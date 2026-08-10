#!/usr/bin/env bash
# Every string check_assessment.py or Plan 1's SKILL.md table depends on modes/assess.md
# defining. Not a pytest file: it is also the copy-paste command in this task's step.
cd /Users/donghanglyu/code_project/job-hunt && python3 -c "
import pathlib
t = pathlib.Path('modes/assess.md').read_text(encoding='utf-8')
for needle in ['scripts/enter_mode.py', '--mode assess',
               '不是对结果的预判', 'not a forecast of the outcome',
               'role_title', 'company', 'seniority', 'location', 'must_haves',
               'nice_to_haves', 'responsibilities', 'keywords', 'company_values_tone',
               'red_flags', 'salary_range', 'application_type',
               'insufficient_evidence', 'how_to_close', 'conventions_rendered',
               '硬性阻断项', '已过复核期', '验收标准', '输出物',
               # Both spellings of every heading and column check_assessment.py keys on.
               # An English card is a supported output; a mode file that names only the
               # Chinese spelling produces one the gate then reports as defective.
               'Hard blockers', '那该怎么办', 'What to do instead',
               'Acceptance criterion', 'Deliverable',
               'apply_anyway', 'reposition', 'skill_sprint', 'side_door', 'change_track']:
    assert needle in t, needle
assert 'language: en' not in t, 'the posting.yaml list must not carry a language field'
print('all anchors present')"
