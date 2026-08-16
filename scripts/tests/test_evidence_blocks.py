import json

import evidence_blocks as eb


def test_ids_are_three_digit_zero_padded_and_prefixed():
    blocks = eb.build_blocks("first paragraph here\n\nsecond paragraph here", "JD", "jd")
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
    text = "\n\n".join("z" * 500 for _ in range(200))
    blocks = eb.build_blocks(text, "CV", "cv")
    assert len(blocks) == eb.MAX_BLOCKS_PER_SOURCE
    assert blocks[-1]["id"] == "CV-080"


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
