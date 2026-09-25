# job-hunt：求人探し、応募書類の作成、面接練習

<p align="center">
  <a href="README.md">简体中文</a> ·
  <a href="README_EN.md">English</a> ·
  <a href="README_JA.md"><strong>日本語</strong></a> ·
  <a href="README_KO.md">한국어</a> ·
  <a href="README_ES.md">Español</a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="ライセンス：MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="Claude Code と Codex 向け" src="https://img.shields.io/badge/agents-Claude_Code_·_Codex-5b5bd6">
  <a href="https://github.com/addsumtech/job-hunt/releases"><img alt="バージョン：v1.1.1" src="https://img.shields.io/badge/release-v1.1.1-1f883d"></a>
  <a href="https://skillhub.cn/skills/user_f486c577/best-job-hunt"><img alt="SkillHub：best-job-hunt" src="https://img.shields.io/badge/SkillHub-best--job--hunt-e8590c"></a>
  <a href="https://clawhub.ai/dong845/skills/job-hunt"><img alt="ClawHub：job-hunt" src="https://img.shields.io/badge/ClawHub-job--hunt-0f766e"></a>
</p>

<p align="center">
  <a href="CHANGELOG.md">変更履歴（中国語）</a>
</p>

<p align="center">
  <img src="docs/assets/hero.jpg" alt="求職の流れを表すイラスト：求人探し、適合性の評価、CV 作成、面接練習">
</p>

job-hunt は Claude Code と Codex で使える求職支援 Skill です。求人探し、応募先の検討、中国語・英語の CV や応募書類の作成、模擬面接による練習を支援します。

希望条件、これまでの経験、求人リンクを渡すと、Agent が情報を整理し、要件を確認して書類の編集とレイアウトの点検を進めます。新卒、キャリアチェンジ、離職期間がある場合、技術職・研究職、海外への応募にも対応したガイドがあります。

## できること

| 機能 | 使う場面 | Agent が行うこと |
|---|---|---|
| **discover · 求人探し** | 希望分野はあるが、応募先が決まっていない | 地域と希望条件で探し、最終候補の募集要項を全文確認して、リンクと助言を整理 |
| **assess · 応募を検討する** | 特定の求人が自分に合うか判断したい | 要件と経験を比較し、応募資格、強み、不足点、準備の負担を説明 |
| **apply · CV と応募書類の作成** | CV を作りたい、または求人に合わせて直したい | 経験から初稿を作成、または既存の CV を編集し、Word/PDF の書式調整と独立レビューを実施 |
| **interview · 模擬面接** | 回答や追加質問への対応を練習したい | 求人と CV に基づいて面接を行い、回答を記録し、伝え方と事実の裏付けを確認 |

各機能は単独でも、必要に応じて組み合わせても使えます。次のステップはあなたが選び、完成した応募書類は自分で提出します。

## 初めて使うとき

### 1. インストールと設定

下の[インストール](#インストール)から方法を一つ選びます。完了したら、Claude Code または Codex で次のように伝えてください。

```text
job-hunt を設定して、普段使っているブラウザーで作業を始めてください。
```

Agent が依存ツールを確認・準備し、必要なブラウザーの接続許可やサイトへのログインを案内します。別の Skill やブラウザー拡張機能は不要です。

### 2. 手元にある資料を渡す

求人探しには希望職種・地域・条件、評価には求人情報と経験を渡します。CV 作成には既存の書類、または学歴・職歴・プロジェクト経験を用意してください。模擬面接には求人情報と CV を使います。不足する情報は Agent が尋ねるので、先に決まった書式へ整理する必要はありません。

### 3. 今回やりたいことを伝える

以下は、それぞれ単独で使える依頼の例です。

```text
job-hunt を使って、上海の AI プロダクトマネージャー求人を探してください。
job-hunt を使って、この求人と私の CV から、応募する価値があるか評価してください。
job-hunt を使って、この経験から中国語と英語の CV を作り、Word と PDF で出力してください。
job-hunt を使って、この求人と私の CV に基づく模擬面接をしてください。
```

## 受け取れる成果物

| 成果物 | 内容 |
|---|---|
| **求職相談レポート（PDF）** | 今回の相談に応じた求人リンク、適合性の分析、強みと不足点、応募の優先順位や次の行動 |
| **求人に合わせた CV（Word/PDF）** | 経験から作成、または求人に合わせて編集した、修正可能な Word と組版済み PDF |
| **追加の応募書類（必要に応じて）** | カバーレター、志望動機書、雇用主指定のフォーム、条件別の応募説明 |
| **面接準備と振り返り（必要に応じて）** | 面接準備メモ、模擬面接の記録、回答の質と事実の裏付けに関する独立評価 |

相談ごとにレポートを作成し、その他の書類は選んだ作業に応じて用意します。地域や雇用主の指定に合わせ、日本の履歴書・職務経歴書、英国 NHS や公務員応募の supporting statement（条件別の説明文）など、適切な形式を使います。

成果物は `~/Downloads/<workspace-name>/` の一つのフォルダーにまとめ、`简历/`（CV）と `报告/`（レポート）に分けます。次の段階でも同じ場所を使うので、最新の書類を見つけやすくなります。

## 内容の確認と改善

### 募集要項の全文と実際の経験

完成版レポートでは、最終候補に残す求人の募集要項をすべて全文確認します。一覧の要約は初期選別用です。取得できない場合は理由と未確認の状態を明記し、確認済みには数えません。

CV の編集と助言は、あなたが提供した経験に基づきます。元のプロフィールを残してコピーを編集し、根拠が不足する点を明示します。スキルや実績の数値を作り上げたり、採用確率を予測したりしません。

### 三つの独立した AI による CV レビュー

| レビューの視点 | 主な確認内容 |
|---|---|
| **採用管理システム（ATS）** | CV を読み取れるか、キーワードが求人要件に対応しているか |
| **採用担当者** | 読みやすさと基本的な応募資格 |
| **採用部門の責任者** | プロジェクト、担当業務、経験が求人要件の根拠になっているか |

通常の CV は指摘に沿って修正し、最大三回までレビューします。実際の経験や資料の追加が必要な不足点は明示したままにします。指定フォームや条件別の説明文は、それぞれの要件に沿って確認します。

### レイアウトと面接の振り返り

納品前に Word/PDF の全ページを確認し、テンプレート、フォント、配置、間隔、改ページを点検します。変更後は再確認し、未解決の書式問題がある場合は完了としません。

模擬面接の後は回答の質と事実の裏付けを別々に独立評価し、補足するとよい詳細や修正すべき CV の表現を示します。

## CVとレポートの出力例

### 英語のCV

架空のCVをPDFから画像化した例です。氏名、学校、企業、プロジェクト、数値はすべてデモ用です。中国語版は[中国語README](README.md)に掲載しています。

<p align="center">
  <a href="docs/assets/examples/cv-en.png"><img src="docs/assets/examples/cv-en.png" width="680" alt="架空の英語CV：学歴、職歴、インターン、プロジェクト、スキル"></a>
</p>

### 求職レポートの抜粋（英語）

2026 年 9 月 11 日に行った実際の求人調査を匿名化し、英語にした抜粋です。求人の判断と準備の例を示します。当時の一部の候補は要約のみでしたが、現在の完成版レポートでは全文確認が必要です。架空の CV はこの判断には使っていません。画像をクリックすると拡大できます。

<p align="center">
  <a href="docs/assets/examples/report-en-01.png"><img src="docs/assets/examples/report-en-01.png" width="49%" alt="匿名化した英語の求職レポート：結論と優先順位"></a>
  <a href="docs/assets/examples/report-en-02.png"><img src="docs/assets/examples/report-en-02.png" width="49%" alt="匿名化した英語の求職レポート：求人との対応、不足する根拠、準備事項"></a>
</p>

## インストール

ローカルコマンドの実行とファイルの読み書きができるエージェント環境、および **Python 3.10+** が必要です。`npx` を使う場合は Node.js/npm も必要です。次の四つから一つを選んでください。

### 方法 1：`npx skills` でインストール

```bash
npx skills add addsumtech/job-hunt
```

表示される案内に従ってエージェントとインストール範囲を選びます。ユーザー全体へのインストールには `-g`、エージェントの指定には `-a claude-code` または `-a codex`、確認の省略には `-y` を使えます。リポジトリのルートが Skill 本体なので、スクリプトと参照ファイルも一緒にインストールします。

### 方法 2：Claude Code プラグインとしてインストール

Claude Code 内で実行します。

```text
/plugin marketplace add addsumtech/job-hunt
/plugin install job-hunt@job-hunt
/reload-plugins
```

呼び出しは `/job-hunt:job-hunt` です。マーケットプレイスを更新する場合は `/plugin marketplace update job-hunt` を実行します。手動コピーとプラグインを併用すると、同じ Skill が二つ表示される場合があります。

### 方法 3：クローンしてシンボリックリンクを作成

ソースを読んだり編集したりする場合に適しています。以下は Claude Code への登録例です。

```bash
git clone https://github.com/addsumtech/job-hunt.git
cd job-hunt
mkdir -p ~/.claude/skills
ln -s "$PWD" ~/.claude/skills/job-hunt
```

Codex では最後の二行の `~/.claude/skills` を `~/.codex/skills` に置き換えます。リンク先が既に存在する場合は、既存のインストールを確認してください。

### 方法 4：SkillHub または ClawHub からインストール

[SkillHub](https://skillhub.cn/skills/user_f486c577/best-job-hunt) または [ClawHub](https://clawhub.ai/dong845/skills/job-hunt) で job-hunt の掲載ページを開き、各プラットフォームの案内に従ってインストールしてください。

## 対応地域と言語

51job、Indeed、LinkedIn、BOSS 直聘などから、対象地域とアクセス条件に合う情報源を選びます。中国市場では大手・中小の民間企業、国有企業、外資系企業などの希望も反映します。牛客は面接体験や選考プロセスの参考に使います。[情報源一覧](references/discovery-sources.md)と[利用ルール](references/source-policy.md)を参照してください。

CV の見出しと個人情報の項目名は、英語、オランダ語、ドイツ語、フランス語、スペイン語、イタリア語、中国語、日本語、韓国語に対応しています。求人探しと評価のレポートには、中国語、英語、日本語、韓国語、スペイン語の[言語別テンプレート](references/report-localization.md)があります。企業・業界調査では公式サイト、ニュース、WeChat 公式アカウント、関連 GitHub プロジェクトなどの[補足情報源](references/supplementary-sources.md)も使えます。

米国、英国、ドイツ、オランダ、中国の市場慣行表を 5 つ収録し、計 38 件の記録に出典、適用範囲、見直し日を付けています。写真、個人情報、応募書式は対象地域と雇用主の指定に合わせ、古い情報や不足する情報は確認を促します。

米国、カナダ、英国、アイルランド、オーストラリア、ニュージーランド向けの通常の CV では、写真と関連する個人情報を標準で省略します。他の認識済み地域では規則に沿って提供済みの情報を使い、地域が未確認なら省略します。

## 設定とよくある質問

### 検索や組版のツールは自分で入れる必要がありますか？

Skill のインストール後、Agent が共通のセットアップから Python パッケージ、Node.js、CDP パッチ付き OpenCLI を準備します。AnySearch クライアントとブラウザーリーダーは同梱され、AnySearch は API キー不要の HTTP API で検索します。CV の組版ツールは必要に応じて準備します。レポートは通常同梱フォントを使いますが、指定フォントを優先し、無断で置き換えません。[環境設定](references/agent-setup.md)を参照してください。

### ブラウザーの接続許可が必要なのはなぜですか？

Agent は標準で CDP（リモートデバッグ接続）を通じて普段の Chrome または Edge に接続し、ログイン状態を使います。初回は `chrome://inspect/#remote-debugging` でリモートデバッグを有効にして接続を許可する必要がある場合があります。Agent が対応状況を確認して案内します。作業中は接続を再利用し、独立した情報源は可能な範囲で同時に検索します。別のブラウザーは明示的に希望した場合だけ使います。[ブラウザー接続](references/daily-browser.md)に詳細があります。

### ログインや認証が必要、または求人を読めない場合は？

Agent はその情報源を一時停止し、ログインや認証を案内します。操作後に「完了したので続けて」と返信してください。引き続き取得できない場合は求人本文を渡すか、未確認の候補として残せます。

まず OpenCLI を検証し、非互換を確認した場合だけ同梱 CDP リーダーを使います。Indeed アダプターは現在米国サイトに接続するため、他国では現地の情報源を優先します。Indeed・51job の既知のパッチは OpenCLI 1.8.7 向けで、確認や復元を依頼できます。サイトの検索欄から直接探すこともできます。[互換性問題の対処](references/opencli-compat.md)を参照してください。

### 元のプロフィールや作業記録はどこに保存されますか？

この Skill は標準で `~/.claude/job-profiles/` を共有の保存先に使います。Claude Code や Codex に最初から付属するフォルダーではなく、プロフィール保存時に必要に応じて作成します。両方の Agent から同じ資料を再利用でき、`JOBHUNT_PROFILES_ROOT` で別の場所も指定できます。元のプロフィールは言語別に、応募用の作業領域は求人別に保存し、納品レポートや CV と分けます。Markdown、該当する場合の `.tex` ソース、確認記録は後の編集や追跡に使います。構成は [REFERENCE.md](REFERENCE.md)を参照してください。

ファイルはローカルに保存されます。モデルへのリクエストとウェブアクセスは、利用する Agent とサービス設定に依存します。

## 検証と関連資料

<details>
<summary>開発者向けのチェック、評価記録、技術文書を見る</summary>

自動チェックは、根拠への参照、元プロフィールの保護、レビュー結果の解析、個人情報の扱い、組版、モード間の引き継ぎなどを対象にしています。

```bash
python3 -m pip install pytest
make check
make eval-lint
```

`make check` は Python テスト、移行時の内容保持チェック、市場慣行表のチェックを実行します。外部ツールを使うテストには対応する環境が必要です。ローカルの Skill インストール検査は必要に応じて有効にできます。

[`evals/`](evals/README.md) には 20 の動作評価シナリオがあります。第 2 回評価（2026-09-05/06）では、15 のシナリオを Skill あり・なしで各一回実行しました（n = 1）。10 項目の動作チェックが、ベースラインの `FAIL` から Skill 使用時の `PASS` に変わりました。結果、未実施の項目、無効になったシナリオは[評価記録](evals/iterations/iteration-2-with-skill.md)に掲載しています。

三つの CV レビュー役は、2026-09-06 に `codex exec` で検証しました。他の Agent の設定方法とテスト範囲は[他の Agent での利用](references/portability.md)を参照してください。

- [SKILL.md](SKILL.md)：モードの振り分けと基本ルール。
- [REFERENCE.md](REFERENCE.md)：構成、作業領域、データ構造、スクリプトの使い方。
- [プロフィール例](assets/profile.example.yaml)と[記述の出典例](assets/claims.example.yaml)：構造化データの形式。
- [動作評価ガイド](evals/README.md)：評価方法と制約。

技術資料は現在、主に英語で記述されています。[MIT License](LICENSE) で公開しています。

</details>
