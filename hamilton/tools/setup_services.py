"""
This script sets up system services for the project. It creates symlinks for service files,
enables them, and starts or restarts them as necessary. Run this script after making changes
to service files or for initial setup.
"""

import argparse
import subprocess
from pathlib import Path

# Top level directory containing .service file defintions
SERVICE_DIR = Path(__file__).parent.parent / "operators"

# systemd system service directory
SYSTEMD_DIR = Path("/etc/systemd/system")


def is_service_active(service_name):
    """Check if a service is active."""
    try:
        subprocess.check_call(["systemctl", "is-active", "--quiet", service_name])
        return True
    except subprocess.CalledProcessError:
        return False


def setup_service(service_path, dry_run=False):
    """Set up a single service."""
    service_name = service_path.name
    print(f"[DRY RUN] Setting up {service_name}..." if dry_run else f"Setting up {service_name}...")

    symlink_path = SYSTEMD_DIR / service_name
    if symlink_path.exists() or symlink_path.is_symlink():
        print(
            f"[DRY RUN] Symlink for {service_name} would be updated."
            if dry_run
            else f"Symlink for {service_name} already exists. Updating."
        )
        if not dry_run:
            symlink_path.unlink()

    if not dry_run:
        symlink_path.symlink_to(service_path)
        subprocess.run(["sudo", "systemctl", "daemon-reload"])
        subprocess.run(["sudo", "systemctl", "enable", service_name])

        if is_service_active(service_name):
            print(f"[DRY RUN] Would restart {service_name}" if dry_run else f"Restarting {service_name}")
            if not dry_run:
                subprocess.run(["sudo", "systemctl", "restart", service_name])
        else:
            print(f"[DRY RUN] Would start {service_name}" if dry_run else f"Starting {service_name}")
            if not dry_run:
                subprocess.run(["sudo", "systemctl", "start", service_name])


def main(dry_run=False):
    service_files = SERVICE_DIR.rglob("*.service")
    for service_path in service_files:
        setup_service(service_path, dry_run=dry_run)
    print(
        "All services have been set up or updated. [DRY RUN]"
        if dry_run
        else "All services have been set up or updated."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up and manage system services.")
    parser.add_argument("--setup", action="store_true", help="Set up all services")
    parser.add_argument("--dry_run", action="store_true", help="Emulate service setup without making changes")
    args = parser.parse_args()

    if args.setup:
        main(dry_run=args.dry_run)
    else:
        parser.print_help()
