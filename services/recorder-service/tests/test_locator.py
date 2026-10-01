from app.recorder.locator import build_candidates, choose_preferred

def test_label_beats_dynamic_id():
    target={"label":"Employee Name","id":"employee_1726819223912","name":"employeeName","tag":"input","type":"text"}
    c=build_candidates(target)
    assert choose_preferred(c)["strategy"] == "label"

def test_testid_is_first():
    target={"testId":"save-employee","label":"Save","id":"save"}
    assert choose_preferred(build_candidates(target))["strategy"] == "testId"
