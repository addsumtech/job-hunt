import json

import evidence_blocks as eb


def test_ids_are_three_digit_zero_padded_and_prefixed():
    blocks, _total = eb.build_blocks(
        "first paragraph here\n\nsecond paragraph here", "JD", "jd")
    assert [b["id"] for b in blocks] == ["JD-001"]
    assert blocks[0]["source"] == "jd"
    # both paragraphs are short, so they repack into one block under the 900 ceiling
    assert "first paragraph here" in blocks[0]["text"]
    assert "second paragraph here" in blocks[0]["text"]


def test_cjk_numbered_list_splits_at_each_cjk_numeral():
    text = "岗位职责如下：\n一、" + "负"*400 + "\n二、" + "责"*400 + "\n三、" + "任"*400
    chunks = eb.split_into_chunks(text)
    assert len(chunks) == 2, chunks
    assert chunks[0].startswith("岗位职责如下：")
    assert "一、" in chunks[0] and "二、" in chunks[0]
    assert chunks[1].startswith("三、")
    assert all(len(c) <= eb.MAX_BLOCK_CHARS for c in chunks)


def test_short_chunks_are_dropped_by_character_count_not_byte_count():
    # Five Chinese characters is fifteen bytes in UTF-8 and ten latin display columns.
    # It must be dropped on the CHARACTER count, exactly as a five-letter latin line
    # would be -- otherwise the same source is chunked differently in two languages.
    assert eb.split_into_chunks("我要找工作") == []
    assert eb.split_into_chunks("short") == []


def test_a_short_paragraph_beside_a_long_one_survives_by_repacking():
    # The floor applies to the finished chunk, not to the paragraph. A short heading
    # merged into the paragraph under it is content, not noise.
    chunks = eb.split_into_chunks("职责\n\n负责磁共振重建流水线的开发与维护工作。")
    assert len(chunks) == 1
    assert chunks[0].startswith("职责")
    assert "负责磁共振重建流水线" in chunks[0]


def test_nine_character_cjk_line_survives():
    chunks = eb.split_into_chunks("我在做磁共振重建研究")
    assert chunks == ["我在做磁共振重建研究"]


def test_over_long_paragraph_is_sentence_split_on_cjk_and_latin_stops():
    paragraph = ("这是第一句。" * 60) + ("This is a sentence. " * 60)
    chunks = eb.split_long_paragraph(paragraph)
    assert len(chunks) > 1
    assert all(len(c) <= eb.MAX_BLOCK_CHARS for c in chunks)
    assert chunks[0].startswith("这是第一句。")


def test_single_sentence_over_the_ceiling_is_hard_sliced():
    paragraph = "x" * 2000
    chunks = eb.split_long_paragraph(paragraph)
    assert [len(c) for c in chunks] == [900, 900, 200]


def test_bullet_list_splits_at_every_bullet():
    text = "\n".join(f"- bullet {i} " + "y" * 500 for i in range(4))
    chunks = eb.split_into_chunks(text)
    assert len(chunks) == 4
    assert all(len(c) <= eb.MAX_BLOCK_CHARS for c in chunks)
    assert [c[:10] for c in chunks] == ["- bullet 0", "- bullet 1",
                                        "- bullet 2", "- bullet 3"]


def test_block_cap_is_eighty_per_source():
    """The cap is a shared-contract parameter and stays. What changed is that the
    count of what the source ACTUALLY produced comes back beside it, so main() can
    say how much was dropped instead of reporting `BLOCKS: 80` and nothing else."""
    text = "\n\n".join("z" * 500 for _ in range(200))
    blocks, total = eb.build_blocks(text, "CV", "cv")
    assert len(blocks) == eb.MAX_BLOCKS_PER_SOURCE
    assert blocks[-1]["id"] == "CV-080"
    assert total > eb.MAX_BLOCKS_PER_SOURCE


def test_flatten_yaml_to_text_is_deterministic_and_readable():
    profile = {"name": "Donghang", "skills": {"infra": ["Docker", "Slurm"]}}
    out = eb.flatten_yaml_to_text(profile)
    assert "name: Donghang" in out
    assert "skills.infra[0]: Docker" in out
    assert "skills.infra[1]: Slurm" in out
    assert eb.flatten_yaml_to_text(profile) == out


def test_main_writes_the_artifact_and_a_receipt(tmp_path):
    (tmp_path / "posting-source.txt").write_text(
        "Requirements\n\n- Five years of C++\n\n- MR physics background", encoding="utf-8")
    (tmp_path / "cv-source.txt").write_text(
        "Experience\n\nBuilt a C++ reconstruction pipeline at Leiden.", encoding="utf-8")
    rc = eb.main(["--workspace", str(tmp_path)])
    assert rc == 0
    data = json.loads((tmp_path / "evidence-blocks.json").read_text(encoding="utf-8"))
    ids = [b["id"] for b in data["blocks"]]
    assert ids[0] == "JD-001"
    assert any(i.startswith("CV-") for i in ids)
    assert set(data["sources"]) == {"jd", "cv"}
    assert len(data["sources"]["jd"]["sha256"]) == 64
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["gate"] for r in receipts] == ["evidence_blocks"]
    # "recorded", not "produced": the composer that reads this receipt is
    # check_assessment.py, whose PASSING_VERDICTS is ("pass", "recorded"), so any
    # other string reads downstream as a failure. Not "baseline_recorded" either —
    # this gate ran and had nothing to report; it did not store a baseline.
    assert receipts[0]["verdict"] == "recorded"


def test_main_exits_two_and_still_leaves_exactly_one_receipt(tmp_path, capsys):
    # "Could not run" is the case where silence looks most like a clean run.
    (tmp_path / "cv-source.txt").write_text("something long enough", encoding="utf-8")
    assert eb.main(["--workspace", str(tmp_path)]) == 2
    assert "posting-source.txt" in capsys.readouterr().err
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(receipts) == 1
    assert receipts[0]["gate"] == "evidence_blocks"
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_workspace_that_does_not_exist_writes_no_journal(tmp_path, capsys):
    # The one documented exception: there is nothing to append to, and creating the
    # directory would leave a journal for a run that never happened.
    missing = tmp_path / "nope"
    assert eb.main(["--workspace", str(missing)]) == 2
    assert not missing.exists()
    assert "does not exist" in capsys.readouterr().err


# ── the 80-block ceiling used to be a silent deletion ────────────────────────

def _long_posting(paragraphs):
    """A posting whose paragraphs cannot repack under the 900-char ceiling, so each
    one becomes its own block and the count is what the caller asked for."""
    return "\n\n".join(f"P{i:03d} " + "x" * 890 for i in range(paragraphs))


def test_a_source_over_the_block_ceiling_says_so(tmp_path):
    """Measured on a 147KB posting: 39% of it was dropped and the receipt read
    `BLOCKS: 81` — indistinguishable from a complete run. Every downstream claim's
    plausibility bound is these blocks; a citation cannot resolve to text that was
    thrown away, so the assessment silently loses the ability to cite the tail."""
    (tmp_path / "posting-source.txt").write_text(_long_posting(100), encoding="utf-8")
    (tmp_path / "cv-source.txt").write_text("Built a C++ pipeline at Leiden.",
                                            encoding="utf-8")
    rc = eb.main(["--workspace", str(tmp_path)])
    assert rc == 0                      # a truncation is reported, not a refusal
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    truncated = [f for f in receipts[0]["findings"] if f.startswith("SOURCE_TRUNCATED:")]
    assert len(truncated) == 1, receipts[0]["findings"]
    assert "posting-source.txt" in truncated[0] or "jd" in truncated[0]
    assert "80" in truncated[0] and "100" in truncated[0]


def test_an_ordinary_posting_is_not_reported_as_truncated(tmp_path):
    """The quiet direction. A posting that fits must produce no SOURCE_TRUNCATED, or
    the finding becomes the line every reader learns to skip."""
    (tmp_path / "posting-source.txt").write_text(_long_posting(20), encoding="utf-8")
    (tmp_path / "cv-source.txt").write_text("Built a C++ pipeline at Leiden.",
                                            encoding="utf-8")
    assert eb.main(["--workspace", str(tmp_path)]) == 0
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert not [f for f in receipts[0]["findings"]
                if f.startswith("SOURCE_TRUNCATED:")]


def test_exactly_the_ceiling_is_not_truncation(tmp_path):
    """Off-by-one, pinned: 80 blocks is a complete run, 81 is not."""
    (tmp_path / "posting-source.txt").write_text(
        _long_posting(eb.MAX_BLOCKS_PER_SOURCE), encoding="utf-8")
    (tmp_path / "cv-source.txt").write_text("Built a C++ pipeline at Leiden.",
                                            encoding="utf-8")
    assert eb.main(["--workspace", str(tmp_path)]) == 0
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert not [f for f in receipts[0]["findings"]
                if f.startswith("SOURCE_TRUNCATED:")]


def test_an_unparseable_yaml_source_is_exit_2_with_a_receipt(tmp_path, capsys):
    (tmp_path / "posting-source.txt").write_text("Requirements\n\nFive years of C++",
                                                 encoding="utf-8")
    profile = tmp_path / "profile.yaml"
    profile.write_text('name: "unclosed\nskills: [C++]\n', encoding="utf-8")
    assert eb.main(["--workspace", str(tmp_path), "--cv", str(profile)]) == 2
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(receipts) == 1
    assert receipts[0]["verdict"] == "could_not_run"
    assert receipts[0]["findings"][0].startswith("UNREADABLE_INPUT: ")
