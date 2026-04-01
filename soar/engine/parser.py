"""
Playbook YAML parser and loader.
Converts YAML files to Playbook Pydantic models.
"""

import logging
from pathlib import Path
from typing import Dict

import yaml

from soar.models.playbook import Playbook

logger = logging.getLogger(__name__)


async def load_playbook(yaml_path: str | Path) -> Playbook:
    """
    Load and parse a single YAML playbook file.

    Args:
        yaml_path: Path to .yaml playbook file

    Returns:
        Parsed Playbook instance

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid or playbook validation fails
    """
    yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"Playbook file not found: {yaml_path}")

    try:
        with open(yaml_path, "r") as f:
            content = yaml.safe_load(f)

        if not content:
            raise ValueError(f"Playbook file is empty: {yaml_path}")

        # Support alternate YAML schema with nested trigger block.
        if "trigger" in content and "trigger_alert_type" not in content:
            trigger = content.get("trigger") or {}
            content["trigger_alert_type"] = trigger.get("alert_type")
            content["min_severity"] = trigger.get("min_severity", "medium")

        # Support alternate condition schema: {if: expr, then: action} / {else: action}.
        for step in content.get("steps", []):
            normalized_conditions = []
            for condition in step.get("on_result", []):
                if "if_expr" in condition:
                    normalized_conditions.append(condition)
                    continue

                if "if" in condition:
                    normalized_conditions.append(
                        {
                            "if_expr": condition.get("if"),
                            "then": condition.get("then"),
                        }
                    )
                    continue

                if "else" in condition:
                    normalized_conditions.append(
                        {
                            "if_expr": None,
                            "then": condition.get("else"),
                        }
                    )
                    continue

                # Keep existing shape for pydantic to validate and error descriptively.
                normalized_conditions.append(condition)

            step["on_result"] = normalized_conditions

        # Validate using Pydantic
        playbook = Playbook(**content)

        logger.info(f"Loaded playbook '{playbook.name}' with {len(playbook.steps)} steps")
        return playbook

    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {yaml_path}: {error}")
    except ValueError as error:
        raise ValueError(f"Playbook validation failed for {yaml_path}: {error}")
    except Exception as error:
        logger.error(f"Error loading playbook {yaml_path}: {error}")
        raise


async def load_all_playbooks(playbooks_dir: str | Path) -> Dict[str, Playbook]:
    """
    Load all YAML playbooks from a directory.

    Args:
        playbooks_dir: Directory containing .yaml files

    Returns:
        Dict keyed by playbook name (not filename)

    Raises:
        FileNotFoundError: If directory doesn't exist
    """
    playbooks_dir = Path(playbooks_dir)

    if not playbooks_dir.exists():
        raise FileNotFoundError(f"Playbooks directory not found: {playbooks_dir}")

    playbooks = {}

    for yaml_file in playbooks_dir.glob("*.yaml"):
        try:
            playbook = await load_playbook(yaml_file)
            playbooks[playbook.name] = playbook
        except Exception as error:
            logger.warning(f"Failed to load {yaml_file}: {error}")

    logger.info(f"Loaded {len(playbooks)} playbooks from {playbooks_dir}")
    return playbooks
