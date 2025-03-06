from pathlib import Path

REPO_DIR = Path(__file__).parent.parent.parent
PROJECT_DIR = REPO_DIR / "hamilton"
RESOURCES_DIR = REPO_DIR / "resources"

ACTIVE_SERVICES_FILE = RESOURCES_DIR / "active_services.yaml"
