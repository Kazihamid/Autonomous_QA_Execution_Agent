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


def test_secret_named_with_the_user_finds_the_per_environment_line():
    src = {"SECRET_PASSWORD_ERPSTAGING_153872": "x"}
    value, used = rs.resolve("SECRET_PASSWORD_153872", "https://erpstaging.brac.net/", {"username": "153872"}, src)
    assert value == "x" and used == "SECRET_PASSWORD_ERPSTAGING_153872"


def test_export_env_fills_passwords_and_test_data_from_the_platform_env_and_nothing_else():
    example = (
        "BASE_URL=https://erpstaging.brac.net\nBROWSER=chromium\n"
        "employeeInfoName__SC=00134572\njobSeparationTypeId__SC=1\nusername__SC=189666\n"
        "SECRET_PASSWORD_189666=\n"
        "# optional: PAYMENT_METHOD\n# optional: EMPLOYEE_PIN\n# optional: jobSeparationTypeId\n# optional: NOT_SET\n"
    )
    source = {
        "SECRET_PASSWORD_ERPSTAGING_189666": "stg-pw", "SECRET_PASSWORD_ENV27": "env27-pw",
        "jobSeparationTypeId": "Retirement", "PAYMENT_METHOD": "Cheque", "EMPLOYEE_PIN": "00077777",
        "UNRELATED_SECRET": "must-not-leave", "PATH": "/usr/bin",
    }
    result = rs.export_env(example, source)
    env = result["env"]
    assert "SECRET_PASSWORD_189666=stg-pw" in env
    assert "jobSeparationTypeId__SC=Retirement" in env and "employeeInfoName__SC=00134572" in env
    assert "PAYMENT_METHOD=Cheque" in env and "EMPLOYEE_PIN=00077777" in env
    assert "must-not-leave" not in env and "/usr/bin" not in env and "NOT_SET" not in env and "env27-pw" not in env
    assert result["missing"] == []


def test_export_env_reports_a_password_that_is_not_in_the_platform_env():
    result = rs.export_env("BASE_URL=https://env27.erp.bracits.net\nusername__SC=1\nSECRET_PASSWORD_1=\n", {})
    assert result["missing"] == ["SECRET_PASSWORD_1"] and "SECRET_PASSWORD_1=\n" in result["env"]
