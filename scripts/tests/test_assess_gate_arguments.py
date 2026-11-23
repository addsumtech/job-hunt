import check_assessment
import check_evidence_refs
import lint_no_prediction
import pytest


@pytest.mark.parametrize("gate", [check_assessment, check_evidence_refs, lint_no_prediction])
@pytest.mark.parametrize("language", [["--lang", "zh"], ["--lang=zh"]])
def test_language_flag_error_names_the_gates_that_accept_it(tmp_path, capsys, gate, language):
    with pytest.raises(SystemExit) as error:
        gate.main(["--workspace", str(tmp_path), *language])
    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "Remove it" in stderr
    assert "count_coverage.py and consistency.py" in stderr
    assert not list(tmp_path.iterdir())
