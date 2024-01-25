"""
This script sets up system services for the project. It creates symlinks for service files,
enables them, and starts or restarts them as necessary. Run this script after making changes
to service files or for initial setup.
"""

import argparse
import subprocess
from pathlib import Path

# Define the path to your project's systemd services
SERVICE_DIR = Path(__file__).parent.parent / "systemd/"

# Define the systemd system service directory
SYSTEMD_DIR = Path("/etc/systemd/system")

def is_service_active(service_name):
    """Check if a service is active."""
    try:
        subprocess.check_call(["systemctl", "is-active", "--quiet", service_name])
        return True
    except subprocess.CalledProcessError:
        return False

def setup_service(service_name):
    """Set up a single service."""
    print(f"Setting up {service_name}...")

    # Check if symlink already exists
    symlink_path = SYSTEMD_DIR / service_name
    if symlink_path.is_symlink():
        print(f"Symlink for {service_name} already exists. Updating.")
        symlink_path.unlink()

    # Create a new symlink for the service
    symlink_path.symlink_to(SERVICE_DIR / service_name)

    # Reload systemd to recognize new service
    subprocess.run(["sudo", "systemctl", "daemon-reload"])

    # Enable the service
    subprocess.run(["sudo", "systemctl", "enable", service_name])

    # Restart the service if it was already running, else start it
    if is_service_active(service_name):
        subprocess.run(["sudo", "systemctl", "restart", service_name])
    else:
        subprocess.run(["sudo", "systemctl", "start", service_name])

def main(setup_all):
    # Setup or update each service
    services = [p.name for p in SERVICE_DIR.iterdir() if p.is_file()]

    for service in services:
        setup_service(service)

    # Remove symlinks for services not in the list
    existing_services = [p.name for p in SYSTEMD_DIR.iterdir() if p.is_symlink()]
    for service in existing_services:
        if service not in services:
            print(f"Removing unused service symlink: {service}")
            (SYSTEMD_DIR / service).unlink()

    print("All services have been set up or updated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Set up and manage system services.')
    parser.add_argument('--setup', action='store_true', help='Set up all services')
    args = parser.parse_args()

    if args.setup:
        main(setup_all=True)
    else:
        parser.print_help()
