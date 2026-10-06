from app import runtime_secrets as rs
from app.main import build_child_env


def test_environment_tag_is_first_host_label():
    assert rs.environment_tag("https://env27.erp.bracits.net/") == "ENV27"
    assert rs.environment_tag("https://erpstaging.brac.net/") == "ERPSTAGING"


def test_candidates_most_specific_first():
    c = rs.candidates("SECRET_PASSWORD", "https://erpstaging.brac.net/", {"username": "153872"})
    assert c == ["SECRET_PASSWORD_ERPSTAGING_153872", "SECRET_PASSWORD_ERPSTAGING", "SECRET_PASSWORD_153872", "SECRET_PASSWORD"]


def test_parse_env_text_handles_quotes_comments_bom_and_dollar():
    text = "\ufeff# c\nA='p$w\"x'\nB=\"two words\"\nexport C=plain\n\nbad line\n"
    assert rs.parse_env_text(text) == {"A": 'p$w"x', "B": "two words", "C": "plain"}


def test_each_erpstaging_user_has_own_password_and_env27_shares_one():
    source = {
        "SECRET_PASSWORD_ERPSTAGING_153872": "stg-for-153872",
        "SECRET_PASSWORD_ERPSTAGING_200001": "stg-for-200001",
        "SECRET_PASSWORD_ENV27": "shared-env27",
        "SECRET_PASSWORD": "fallback",
    }
    stg = "https://erpstaging.brac.net/"
    env27 = "https://env27.erp.bracits.net/"
    assert build_child_env(stg, ["SECRET_PASSWORD"], {"username": "153872"}, source)["SECRET_PASSWORD"] == "stg-for-153872"
    assert build_child_env(stg, ["SECRET_PASSWORD"], {"username": "200001"}, source)["SECRET_PASSWORD"] == "stg-for-200001"
    for user in ("153872", "200001", "999999"):
        assert build_child_env(env27, ["SECRET_PASSWORD"], {"username": user}, source)["SECRET_PASSWORD"] == "shared-env27"
    # a user with no specific entry on erpStaging falls back to the generic name
    assert build_child_env(stg, ["SECRET_PASSWORD"], {"username": "777"}, source)["SECRET_PASSWORD"] == "fallback"


def test_notes_name_the_variable_but_never_the_value():
    notes = []
    build_child_env("https://env27.erp.bracits.net/", ["SECRET_PASSWORD"], {"username": "1"}, {"SECRET_PASSWORD_ENV27": "topsecret"}, notes)
    assert notes == ["[runner] secret SECRET_PASSWORD taken from SECRET_PASSWORD_ENV27"]
    assert "topsecret" not in "".join(notes)


def test_secrets_file_is_reread_each_time(tmp_path, monkeypatch):
    f = tmp_path / ".env.runtime"
    f.write_text("SECRET_PASSWORD_ENV27='one'\n", encoding="utf-8")
    assert rs.load_source(str(f))["SECRET_PASSWORD_ENV27"] == "one"
    f.write_text("SECRET_PASSWORD_ENV27='two'\n", encoding="utf-8")
    assert rs.load_source(str(f))["SECRET_PASSWORD_ENV27"] == "two"
