from physical_agent.protocol.workspace import Workspace


def test_workspace_init_creates_all_files(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    for filename in Workspace.filenames.values():
        assert (workspace.path / filename).exists()
    assert workspace.artifacts_path.exists()


def test_workspace_revision_increments(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    before = workspace.read_task()["metadata"]["revision"]
    workspace.write_task("A new task")
    after = workspace.read_task()["metadata"]["revision"]
    assert after == before + 1


def test_workspace_log_append(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    workspace.append_log("hello", actor="test")
    content = workspace.file("log").read_text(encoding="utf-8")
    assert "hello" in content
    assert "**test**" in content

