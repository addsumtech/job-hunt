# job-hunt: 공고 탐색, 이력서 작성, 면접 연습

<p align="center">
  <a href="README.md">简体中文</a> ·
  <a href="README_EN.md">English</a> ·
  <a href="README_JA.md">日本語</a> ·
  <a href="README_KO.md"><strong>한국어</strong></a> ·
  <a href="README_ES.md">Español</a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="라이선스: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="Claude Code 및 Codex용" src="https://img.shields.io/badge/agents-Claude_Code_·_Codex-5b5bd6">
  <a href="https://github.com/addsumtech/job-hunt/releases"><img alt="버전: v1.0.1" src="https://img.shields.io/badge/release-v1.0.1-1f883d"></a>
  <a href="https://skillhub.cn/skills/user_f486c577/best-job-hunt"><img alt="SkillHub: best-job-hunt" src="https://img.shields.io/badge/SkillHub-best--job--hunt-e8590c"></a>
  <a href="https://clawhub.ai/dong845/skills/job-hunt"><img alt="ClawHub: job-hunt" src="https://img.shields.io/badge/ClawHub-job--hunt-0f766e"></a>
</p>

<p align="center">
  <a href="CHANGELOG.md">변경 기록 (중국어)</a>
</p>

<p align="center">
  <img src="docs/assets/hero.jpg" alt="취업 과정 일러스트: 공고 탐색, 적합성 평가, 이력서 작성과 면접 연습">
</p>

job-hunt는 Claude Code와 Codex에서 사용하는 취업 지원 Skill입니다. 적합한 공고를 찾고 지원할지 판단하며, 중국어·영어 이력서와 지원 서류를 작성하고 모의 면접으로 답변을 연습할 수 있습니다.

목표, 경력 또는 공고 링크를 주면 Agent가 정보를 정리하고 요건을 확인한 뒤 문서를 수정하고 서식을 검토합니다. 신입 지원, 직무 전환, 경력 공백, 기술·연구 직군과 해외 취업에 맞는 안내도 제공합니다.

## 어떤 일을 도와주나요?

| 기능 | 사용하는 상황 | Agent가 하는 일 |
|---|---|---|
| **discover · 공고 탐색** | 희망 분야는 있지만 적합한 공고를 찾지 못했을 때 | 지역과 선호 조건으로 검색하고 최종 후보의 상세 공고를 모두 읽은 뒤 링크와 조언을 정리 |
| **assess · 지원 여부 판단** | 특정 공고가 자신에게 맞는지 알고 싶을 때 | 요건과 경력을 비교해 필수 자격, 강점, 부족한 점, 준비에 필요한 노력을 설명 |
| **apply · 이력서와 지원 서류 작성** | 새 이력서나 직무에 맞춘 서류가 필요할 때 | 경력으로 초안을 만들거나 기존 이력서를 수정하고 Word/PDF 편집과 독립 검토를 진행 |
| **interview · 모의 면접** | 답변과 후속 질문을 연습하고 싶을 때 | 공고와 이력서로 면접을 진행하고 답변을 기록해 전달력과 사실 근거를 검토 |

각 기능은 따로 사용하거나 필요에 따라 연결할 수 있습니다. 다음 단계는 사용자가 선택하고 완성된 지원 서류도 직접 제출합니다.

## 처음 사용하기

### 1. 설치와 설정

아래 [설치](#설치)에서 한 가지 방법을 선택하세요. 설치한 뒤 Claude Code나 Codex에서 이렇게 요청합니다.

```text
job-hunt를 설정하고 평소 사용하는 브라우저로 작업을 시작해 주세요.
```

Agent가 필요한 도구를 확인하고 준비한 뒤 브라우저 연결 승인이나 사이트 로그인을 안내합니다. 다른 Skill이나 브라우저 확장 프로그램을 추가로 설치할 필요는 없습니다.

### 2. 가지고 있는 자료 전달하기

공고 탐색에는 희망 직무·지역·선호 조건을, 평가에는 공고와 경력을 전달하세요. 이력서 작성에는 기존 문서 또는 학력·경력·프로젝트 경험을, 모의 면접에는 공고와 이력서를 사용합니다. 부족한 정보는 Agent가 물어보므로 미리 정해진 양식으로 정리할 필요는 없습니다.

### 3. 이번에 할 일 요청하기

아래 문장은 각각 따로 사용할 수 있는 예시입니다.

```text
job-hunt로 상하이의 AI 프로덕트 매니저 공고를 찾아 주세요.
job-hunt로 이 공고와 제 이력서를 보고 지원할 만한지 평가해 주세요.
job-hunt로 이 경험을 중국어·영어 이력서로 만들고 Word와 PDF로 제공해 주세요.
job-hunt로 이 공고와 제 이력서를 바탕으로 모의 면접을 진행해 주세요.
```

## 받을 수 있는 결과물

| 결과물 | 내용 |
|---|---|
| **취업 상담 보고서(PDF)** | 이번 작업에 맞춘 공고 링크, 적합성 분석, 강점과 부족한 점, 지원 우선순위 또는 다음 행동 |
| **맞춤 이력서(Word/PDF)** | 경력으로 새로 만들거나 공고에 맞춰 수정한 편집 가능한 Word 파일과 조판된 PDF |
| **추가 지원 서류(요청 시)** | 커버레터, 지원 동기서, 고용주 지정 양식 또는 요건별 지원 설명서 |
| **면접 준비와 피드백(요청 시)** | 면접 준비 자료, 모의 면접 기록, 답변의 질과 사실 근거에 관한 독립 평가 |

상담마다 보고서를 제공하고 나머지 자료는 선택한 작업에 맞춰 생성합니다. 지역과 고용주의 요구에 따라 일본의 이력서·경력기술서나 영국 NHS·공무원 지원의 supporting statement(요건별 설명서) 등 적절한 형식을 사용합니다.

결과물은 `~/Downloads/<workspace-name>/`의 한 폴더에 모으고 `简历/`(이력서)와 `报告/`(보고서)로 나눕니다. 다음 단계에서도 같은 위치를 사용하므로 최신 자료를 찾기 쉽습니다.

## 자료를 확인하고 개선하는 방법

### 상세 공고와 실제 경력

완성된 취업 보고서에는 최종 후보로 남긴 모든 공고의 상세 내용을 읽어야 합니다. 목록 요약은 초기 선별용입니다. 실제로 접근할 수 없다면 이유와 미확인 상태를 표시하며 확인 완료로 계산하지 않습니다.

이력서 수정과 조언은 사용자가 제공한 경력을 근거로 합니다. 원본 프로필은 보존하고 사본을 수정하며 부족한 근거를 명시합니다. 기술이나 성과 수치를 꾸며내거나 채용 확률을 예측하지 않습니다.

### 독립된 세 AI 관점의 이력서 검토

| 검토 관점 | 주요 확인 내용 |
|---|---|
| **지원자 관리 시스템(ATS)** | 이력서를 시스템이 읽을 수 있는지, 키워드가 채용 요건과 연결되는지 |
| **채용 담당자** | 가독성과 기본 지원 자격 |
| **현업 책임자** | 프로젝트, 담당 업무와 실제 경험이 채용 요건을 뒷받침하는지 |

일반 이력서는 피드백에 따라 수정하고 최대 세 회차까지 검토합니다. 실제 경험이나 자료를 추가해야 해결되는 부족한 점은 명시합니다. 지정 양식과 요건별 설명서는 각각의 요구 사항에 맞춰 확인합니다.

### 서식과 면접 피드백

전달 전 Word/PDF의 모든 페이지를 확인하고 템플릿, 글꼴, 정렬, 간격, 페이지 나눔을 점검합니다. 수정한 뒤에는 다시 검토하며 해결되지 않은 서식 문제가 있으면 완료로 표시하지 않습니다.

모의 면접 뒤에는 답변의 질과 사실 근거를 각각 독립 평가하고 보충할 내용과 수정할 이력서 표현을 안내합니다.

## 이력서와 보고서 예시

### 영어 이력서

가상 이력서 PDF를 이미지로 변환한 예시입니다. 이름, 학교, 회사, 프로젝트와 수치는 모두 시연용입니다. 중국어 버전은 [중국어 README](README.md)에서 볼 수 있습니다.

<p align="center">
  <a href="docs/assets/examples/cv-en.png"><img src="docs/assets/examples/cv-en.png" width="680" alt="가상 영어 이력서: 학력, 경력, 인턴십, 프로젝트와 역량"></a>
</p>

### 구직 보고서 발췌본（영어）

2026년 9월 11일 실제 구직 조사에서 개인정보를 익명화하고 영어로 옮긴 발췌본으로, 공고 판단과 준비의 예시입니다. 당시 일부 후보는 요약만 있었지만 현재 완성 보고서는 상세 공고 확인이 필수입니다. 가상 이력서는 이 판단에 사용하지 않았습니다. 이미지를 클릭하면 확대됩니다.

<p align="center">
  <a href="docs/assets/examples/report-en-01.png"><img src="docs/assets/examples/report-en-01.png" width="49%" alt="익명화된 영어 구직 보고서: 결론과 우선순위"></a>
  <a href="docs/assets/examples/report-en-02.png"><img src="docs/assets/examples/report-en-02.png" width="49%" alt="익명화된 영어 구직 보고서: 공고별 분석과 준비 사항"></a>
</p>

## 설치

로컬 명령을 실행하고 파일을 읽고 쓸 수 있는 에이전트 환경과 **Python 3.10+**가 필요합니다. `npx` 설치에는 Node.js/npm도 필요합니다. 아래 네 가지 중 하나를 선택하세요.

### 방법 1: `npx skills`로 설치

```bash
npx skills add addsumtech/job-hunt
```

안내에 따라 에이전트와 설치 범위를 선택합니다. 사용자 전체 범위로 설치하려면 `-g`, 에이전트를 지정하려면 `-a claude-code` 또는 `-a codex`, 확인 프롬프트를 건너뛰려면 `-y`를 사용합니다. 저장소 루트가 Skill 본체이므로 스크립트와 참고 파일도 함께 설치해야 합니다.

### 방법 2: Claude Code 플러그인으로 설치

Claude Code 안에서 실행합니다.

```text
/plugin marketplace add addsumtech/job-hunt
/plugin install job-hunt@job-hunt
/reload-plugins
```

`/job-hunt:job-hunt`로 호출합니다. 마켓플레이스 갱신에는 `/plugin marketplace update job-hunt`를 사용합니다. 수동 복사본과 플러그인을 함께 설치하면 같은 Skill이 두 번 표시될 수 있습니다.

### 방법 3: 저장소 복제 후 심볼릭 링크 생성

소스를 읽거나 수정하려는 경우에 적합합니다. 아래는 Claude Code에 등록하는 예시입니다.

```bash
git clone https://github.com/addsumtech/job-hunt.git
cd job-hunt
mkdir -p ~/.claude/skills
ln -s "$PWD" ~/.claude/skills/job-hunt
```

Codex에서는 마지막 두 줄의 `~/.claude/skills`를 `~/.codex/skills`로 바꿉니다. 대상 경로가 이미 존재하면 기존 설치를 먼저 확인하세요.

### 방법 4: SkillHub 또는 ClawHub에서 설치

[SkillHub](https://skillhub.cn/skills/user_f486c577/best-job-hunt) 또는 [ClawHub](https://clawhub.ai/dong845/skills/job-hunt)에서 job-hunt 등록 페이지를 열고 해당 플랫폼의 설치 안내를 따르세요.

## 지원 지역과 언어

51job, Indeed, LinkedIn, BOSS 直聘 등에서 목표 지역과 접근 조건에 맞는 정보원을 선택합니다. 중국 시장에서는 대형·중소 민간기업, 국유기업, 외국계 기업 등의 선호도 반영합니다. 牛客는 면접 경험과 채용 절차를 참고할 때 사용합니다. [정보원 목록](references/discovery-sources.md)과 [이용 규칙](references/source-policy.md)을 참고하세요.

이력서 제목과 개인정보 항목명은 영어, 네덜란드어, 독일어, 프랑스어, 스페인어, 이탈리아어, 중국어, 일본어, 한국어를 지원합니다. 공고 탐색과 평가 보고서는 중국어, 영어, 일본어, 한국어, 스페인어의 [언어별 템플릿](references/report-localization.md)을 사용합니다. 기업·업계 조사에는 공식 사이트, 뉴스, WeChat 공식 계정과 관련 GitHub 프로젝트 등의 [추가 정보원](references/supplementary-sources.md)도 활용합니다.

미국, 영국, 독일, 네덜란드, 중국의 시장 관행 표 5개에 총 38개 항목이 있으며 출처, 적용 범위, 검토 날짜가 붙어 있습니다. 사진, 개인정보와 지원 양식은 목표 지역 및 고용주 요구에 맞추고 오래되거나 빠진 정보는 확인을 요청합니다.

미국, 캐나다, 영국, 아일랜드, 호주, 뉴질랜드의 일반 이력서는 기본적으로 사진과 관련 개인정보를 생략합니다. 그 밖의 확인된 지역은 해당 규칙에 따라 제공된 정보를 사용하며 지역이 미확인이라면 생략합니다.

## 설정과 자주 묻는 질문

### 검색·편집 도구를 직접 설치해야 하나요?

Skill 설치 후 Agent가 통합 설정 도구로 Python 패키지, Node.js, CDP 패치가 적용된 OpenCLI를 준비합니다. AnySearch 클라이언트와 브라우저 리더가 포함되어 있으며 AnySearch는 API 키 없이 HTTP API로 검색합니다. 이력서 편집 도구는 필요할 때 준비합니다. 보고서는 기본 포함 글꼴을 쓰지만 명시적으로 지정한 글꼴을 우선하며 임의로 바꾸지 않습니다. [환경 설정](references/agent-setup.md)을 참고하세요.

### 브라우저 연결 승인은 왜 필요한가요?

Agent는 기본적으로 CDP(원격 디버깅 연결)로 평소 사용하는 Chrome 또는 Edge에 접근해 로그인 상태를 재사용합니다. 처음에는 `chrome://inspect/#remote-debugging`에서 원격 디버깅을 켜고 연결을 승인해야 할 수 있습니다. Agent가 지원 여부를 확인하고 안내합니다. 작업 중 연결을 재사용하고 독립적인 정보원은 가능한 범위에서 동시에 검색합니다. 별도 브라우저는 명시적으로 요청한 경우에만 사용합니다. [브라우저 연결](references/daily-browser.md)에 자세히 설명되어 있습니다.

### 로그인·인증이 필요하거나 공고를 읽을 수 없다면요?

Agent가 해당 정보원을 일시 중지하고 로그인이나 인증을 안내합니다. 마친 뒤 “완료했으니 계속해”라고 답하세요. 계속 접근할 수 없다면 공고 본문을 제공하거나 미확인 후보로 남길 수 있습니다.

먼저 OpenCLI를 검증하고 호환성 문제가 확인된 경우에만 내장 CDP 리더를 사용합니다. Indeed 어댑터는 현재 미국 사이트에 연결하므로 다른 시장은 현지 정보원을 우선합니다. 알려진 Indeed·51job 패치는 OpenCLI 1.8.7용이며 확인하거나 되돌릴 수 있습니다. 사이트 검색창을 직접 사용하는 것도 가능합니다. [호환성 문제 해결](references/opencli-compat.md)을 참고하세요.

### 원본 프로필과 작업 기록은 어디에 보관되나요?

이 Skill은 기본 공유 저장 위치로 `~/.claude/job-profiles/`를 사용합니다. Claude Code나 Codex에 원래 포함된 폴더가 아니라 프로필을 저장할 때 필요에 따라 생성합니다. 두 Agent가 자료를 재사용하도록 같은 위치를 쓰며 `JOBHUNT_PROFILES_ROOT`로 바꿀 수 있습니다. 원본 프로필은 언어별로, 지원 작업 공간은 공고별로 나누고 전달된 보고서·이력서와 따로 보관합니다. Markdown, 해당하는 경우의 `.tex` 소스와 검사 기록은 이후 수정과 추적에 사용합니다. 구조는 [REFERENCE.md](REFERENCE.md)를 참고하세요.

파일은 로컬에 저장됩니다. 모델 호출과 웹 접근은 사용하는 Agent 및 서비스 설정에 따라 이루어집니다.

## 검증과 참고 자료

<details>
<summary>개발자 검사, 평가 기록과 기술 문서 보기</summary>

자동 검사는 근거 참조, 원본 프로필 보호, 검토 결과 파싱, 개인정보 처리, 조판, 모드 간 전환 등을 다룹니다.

```bash
python3 -m pip install pytest
make check
make eval-lint
```

`make check`는 Python 테스트, 마이그레이션 내용 보존 검사, 시장 관행 표 검사를 실행합니다. 외부 도구를 사용하는 테스트는 해당 환경이 필요하며 로컬 Skill 설치 검사는 선택해서 실행할 수 있습니다.

[`evals/`](evals/README.md)에는 행동 평가 시나리오 20개가 있습니다. 2차 평가(2026-09-05/06)에서는 15개 시나리오를 Skill 사용·미사용으로 각각 한 번 실행했습니다(n = 1). 행동 검사 10개가 기준 실행의 `FAIL`에서 Skill 사용 시 `PASS`로 바뀌었습니다. 결과, 미실행 항목, 무효 시나리오는 [평가 기록](evals/iterations/iteration-2-with-skill.md)에 정리되어 있습니다.

세 이력서 검토자는 2026-09-06에 `codex exec`로 검증했습니다. 다른 Agent의 설정 방법과 테스트 범위는 [다른 Agent에서 사용하기](references/portability.md)를 참고하세요.

- [SKILL.md](SKILL.md): 모드 선택과 핵심 규칙.
- [REFERENCE.md](REFERENCE.md): 구조, 작업 공간, 데이터 형식, 스크립트 사용법.
- [프로필 예시](assets/profile.example.yaml)와 [서술 출처 예시](assets/claims.example.yaml): 구조화된 데이터 형식.
- [행동 평가 안내](evals/README.md): 평가 방법과 한계.

현재 기술 자료는 주로 영어로 작성되어 있습니다. [MIT License](LICENSE)로 배포합니다.

</details>
