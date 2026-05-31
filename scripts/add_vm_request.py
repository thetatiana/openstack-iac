#!/usr/bin/env python3

import os
import re
import sys
from pathlib import Path

import yaml

YAML_PATH = Path("vm-requests.yaml")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        print(f"ERROR: Required environment variable {name} is empty", file=sys.stderr)
        sys.exit(1)
    return value.strip()


def optional_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "y", "1"}:
        return True
    if normalized in {"false", "no", "n", "0"}:
        return False
    print(f"ERROR: VM_FLOATING_IP must be true/false, got: {value}", file=sys.stderr)
    sys.exit(1)


def validate_vm_name(name: str) -> None:
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,62}$", name):
        print(
            "ERROR: VM_NAME must be 2-63 chars and contain only letters, numbers, dots, underscores or hyphens",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    vm_name = required_env("VM_NAME")
    validate_vm_name(vm_name)

    vm = {
        "image": required_env("VM_IMAGE"),
        "flavor": required_env("VM_FLAVOR"),
        "network": required_env("VM_NETWORK"),
        "keypair": required_env("VM_KEYPAIR"),
        "floating_ip": parse_bool(required_env("VM_FLOATING_IP")),
    }

    admin_cidr = optional_env("VM_ADMIN_CIDR")
    if admin_cidr:
        vm["admin_cidr"] = admin_cidr

    if YAML_PATH.exists():
        with YAML_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    if "vms" not in data or data["vms"] is None:
        data["vms"] = {}

    if vm_name in data["vms"]:
        print(f"ERROR: VM '{vm_name}' already exists in vm-requests.yaml", file=sys.stderr)
        print("Change VM_NAME or delete/update the existing entry manually.", file=sys.stderr)
        sys.exit(1)

    data["vms"][vm_name] = vm

    with YAML_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )

    print(f"Added VM request: {vm_name}")


if __name__ == "__main__":
    main()