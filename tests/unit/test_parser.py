"""Unit tests for YAML playbook parser."""

import tempfile
from pathlib import Path

import pytest

from soar.engine.parser import load_all_playbooks, load_playbook


@pytest.mark.asyncio
async def test_load_playbook_success():
    """Test: load_playbook() parses valid YAML file successfully."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            """
name: test_playbook
trigger_alert_type: phishing
min_severity: medium
steps:
  - id: step1
    connector: mock_jira
    input_field: source_ip
    timeout: 30
    retries: 3
    on_result:
      - if_expr: null
        then: close
"""
        )
        f.flush()

        playbook = await load_playbook(f.name)

    assert playbook.name == "test_playbook"
    assert playbook.trigger_alert_type == "phishing"
    assert playbook.min_severity == "medium"
    assert len(playbook.steps) == 1
    assert playbook.steps[0].id == "step1"

    Path(f.name).unlink()


@pytest.mark.asyncio
async def test_load_playbook_invalid_yaml():
    """Test: load_playbook() with invalid YAML raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("{ invalid yaml [[[")
        f.flush()

        with pytest.raises(Exception):  # yaml.YAMLError
            await load_playbook(f.name)

    Path(f.name).unlink()


@pytest.mark.asyncio
async def test_load_playbook_missing_required_field():
    """Test: load_playbook() with missing required field raises ValidationError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            """
name: test_playbook
# Missing trigger_alert_type
min_severity: medium
steps: []
"""
        )
        f.flush()

        with pytest.raises(Exception):  # pydantic ValidationError
            await load_playbook(f.name)

    Path(f.name).unlink()


@pytest.mark.asyncio
async def test_load_playbook_empty_steps():
    """Test: load_playbook() with empty steps raises ValidationError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            """
name: test_playbook
trigger_alert_type: phishing
min_severity: medium
steps: []
"""
        )
        f.flush()

        with pytest.raises(Exception):  # pydantic ValidationError - min 1 step required
            await load_playbook(f.name)

    Path(f.name).unlink()


@pytest.mark.asyncio
async def test_load_playbook_duplicate_step_ids():
    """Test: load_playbook() with duplicate step IDs raises ValidationError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            """
name: test_playbook
trigger_alert_type: phishing
min_severity: medium
steps:
  - id: step1
    connector: mock_jira
    input_field: source_ip
    timeout: 30
    retries: 3
    on_result:
      - then: close
  - id: step1
    connector: mock_jira
    input_field: destination_ip
    timeout: 30
    retries: 3
    on_result:
      - then: close
"""
        )
        f.flush()

        with pytest.raises(Exception):  # pydantic ValidationError - unique step IDs
            await load_playbook(f.name)

    Path(f.name).unlink()


@pytest.mark.asyncio
async def test_load_playbook_invalid_timeout():
    """Test: load_playbook() with timeout <= 0 raises ValidationError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            """
name: test_playbook
trigger_alert_type: phishing
min_severity: medium
steps:
  - id: step1
    connector: mock_jira
    input_field: source_ip
    timeout: 0
    retries: 3
    on_result:
      - then: close
"""
        )
        f.flush()

        with pytest.raises(Exception):  # pydantic ValidationError - timeout > 0
            await load_playbook(f.name)

    Path(f.name).unlink()


@pytest.mark.asyncio
async def test_load_playbook_invalid_retries():
    """Test: load_playbook() with negative retries raises ValidationError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            """
name: test_playbook
trigger_alert_type: phishing
min_severity: medium
steps:
  - id: step1
    connector: mock_jira
    input_field: source_ip
    timeout: 30
    retries: -1
    on_result:
      - then: close
"""
        )
        f.flush()

        with pytest.raises(Exception):  # pydantic ValidationError - retries >= 0
            await load_playbook(f.name)

    Path(f.name).unlink()


@pytest.mark.asyncio
async def test_load_all_playbooks(tmp_path):
    """Test: load_all_playbooks() loads multiple YAML files from directory."""
    # Create 2 test playbooks
    playbook1 = tmp_path / "playbook1.yaml"
    playbook1.write_text(
        """
name: playbook1
trigger_alert_type: phishing
min_severity: medium
steps:
  - id: step1
    connector: mock_jira
    input_field: source_ip
    timeout: 30
    retries: 3
    on_result:
      - then: close
"""
    )

    playbook2 = tmp_path / "playbook2.yaml"
    playbook2.write_text(
        """
name: playbook2
trigger_alert_type: malware
min_severity: high
steps:
  - id: step1
    connector: mock_jira
    input_field: source_ip
    timeout: 30
    retries: 3
    on_result:
      - then: close
"""
    )

    playbooks = await load_all_playbooks(str(tmp_path))

    assert len(playbooks) == 2
    assert "playbook1" in playbooks
    assert "playbook2" in playbooks
    assert playbooks["playbook1"].trigger_alert_type == "phishing"
    assert playbooks["playbook2"].trigger_alert_type == "malware"


@pytest.mark.asyncio
async def test_load_all_playbooks_empty_dir(tmp_path):
    """Test: load_all_playbooks() with empty directory returns empty dict."""
    playbooks = await load_all_playbooks(str(tmp_path))

    assert playbooks == {}


@pytest.mark.asyncio
async def test_load_all_playbooks_skips_non_yaml(tmp_path):
    """Test: load_all_playbooks() skips non-.yaml files."""
    playbook = tmp_path / "playbook.yaml"
    playbook.write_text(
        """
name: playbook
trigger_alert_type: phishing
min_severity: medium
steps:
  - id: step1
    connector: mock_jira
    input_field: source_ip
    timeout: 30
    retries: 3
    on_result:
      - then: close
"""
    )

    # Create a non-yaml file
    (tmp_path / "readme.txt").write_text("not a playbook")

    playbooks = await load_all_playbooks(str(tmp_path))

    assert len(playbooks) == 1
    assert "playbook" in playbooks


@pytest.mark.asyncio
async def test_load_all_playbooks_skips_invalid_files(tmp_path):
    """Test: load_all_playbooks() skips invalid YAML files (non-blocking)."""
    valid_playbook = tmp_path / "valid.yaml"
    valid_playbook.write_text(
        """
name: valid
trigger_alert_type: phishing
min_severity: medium
steps:
  - id: step1
    connector: mock_jira
    input_field: source_ip
    timeout: 30
    retries: 3
    on_result:
      - then: close
"""
    )

    invalid_playbook = tmp_path / "invalid.yaml"
    invalid_playbook.write_text("{ invalid yaml [[[")

    # Should load valid playbook and skip invalid one (non-blocking)
    # Note: actual implementation behavior depends on error handling strategy
    playbooks = await load_all_playbooks(str(tmp_path))

    # At minimum, valid playbook should be loaded
    assert "valid" in playbooks
