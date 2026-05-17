import pytest
import yaml

from physical_agent.drivers.manifest import load_driver_manifest, validate_driver_config
from physical_agent.drivers.templates import manifest_template


def test_parse_physical_driver_yaml(tmp_path):
    driver_dir = tmp_path / "driver"
    driver_dir.mkdir()
    (driver_dir / "physical_driver.yaml").write_text(
        manifest_template("my_driver", "MyDriver"),
        encoding="utf-8",
    )
    manifest = load_driver_manifest(driver_dir)
    assert manifest.name == "my_driver"
    assert manifest.entrypoint.class_name == "MyDriver"


def test_manifest_required_fields(tmp_path):
    driver_dir = tmp_path / "driver"
    driver_dir.mkdir()
    (driver_dir / "physical_driver.yaml").write_text(
        yaml.safe_dump({"schema": "physical-agent/driver/v1"}),
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_driver_manifest(driver_dir)


def test_validate_robot_config_against_schema(tmp_path):
    driver_dir = tmp_path / "driver"
    driver_dir.mkdir()
    (driver_dir / "physical_driver.yaml").write_text(
        """schema: physical-agent/driver/v1
name: strict_driver
version: 0.1.0
entrypoint:
  module: driver
  class: StrictDriver
robot:
  kind: arm
  supports_simulation: true
config_schema:
  type: object
  required: [port]
  properties:
    port:
      type: string
  additionalProperties: false
dependencies:
  python: []
capability_contract:
  source: runtime
""",
        encoding="utf-8",
    )
    manifest = load_driver_manifest(driver_dir)
    validate_driver_config(manifest, {"port": "COM3"})
    with pytest.raises(ValueError):
        validate_driver_config(manifest, {})

