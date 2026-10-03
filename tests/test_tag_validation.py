import tag_validation


def test_diagnose_missing_references_and_variables():
    warnings = tag_validation.diagnose_template(
        "echo !missing[2] !42 $UNDEFINED",
        current_tag="example",
        commands=[],
        variables={"PATH"},
    )
    assert "Missing command reference !missing[2]" in warnings
    assert "Missing command reference !42" in warnings
    assert "Variable $UNDEFINED is not currently defined" in warnings


def test_diagnose_does_not_treat_shell_text_as_runbook_metadata():
    warnings = tag_validation.diagnose_template(
        "echo run:auto",
        current_tag="example",
        commands=[],
        variables=set(),
    )
    assert not any("run:auto" in warning for warning in warnings)


def test_diagnose_warns_about_comment_run_auto_and_known_risks():
    warnings = tag_validation.diagnose_template(
        "kubectl delete pod demo",
        current_tag="example",
        commands=[{"tag": "example", "comment": "run:auto"}],
        variables=set(),
    )
    assert any("run:auto" in warning for warning in warnings)
    assert any("kubectl delete" in warning for warning in warnings)


def test_diagnose_accepts_existing_references_and_variables():
    warnings = tag_validation.diagnose_template(
        "echo $HOME !target[1] !12",
        current_tag="example",
        commands=[
            {"id": 12, "tag": "target", "tid": 1, "comment": ""},
        ],
        variables={"HOME"},
    )
    assert warnings == []
