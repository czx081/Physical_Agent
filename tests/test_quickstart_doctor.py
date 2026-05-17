from physical_agent.doctor import doctor_ok, run_doctor
from physical_agent.quickstart import setup_project


def test_doctor_reports_missing_config(tmp_path):
    checks = run_doctor(tmp_path / "physical-agent.yaml")
    assert not doctor_ok(checks)
    assert any(check.name == "config" and not check.ok for check in checks)


def test_setup_project_smoke_test(tmp_path):
    result = setup_project(tmp_path / "physical-agent.yaml", smoke_test=True)
    assert result["doctor_ok"] is True
    assert result["smoke_test"]["ok"] is True
    assert result["smoke_test"]["red_block_location"] == "tray"

