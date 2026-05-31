#!/usr/bin/env python3

import os
from pathlib import Path

import yaml


ROOT = Path.cwd()


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def bool_from_string(value: str) -> bool:
    normalized = value.strip().lower()

    if normalized == "true":
        return True

    if normalized == "false":
        return False

    raise SystemExit(f"Expected true/false value, got: {value}")


def load_yaml(path: Path, default: dict) -> dict:
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data if data is not None else default


def save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


def build_vm_spec() -> dict:
    return {
        "image": require_env("VM_IMAGE"),
        "flavor": require_env("VM_FLAVOR"),
        "network": require_env("VM_NETWORK"),
        "keypair": require_env("VM_KEYPAIR"),
        "floating_ip": bool_from_string(require_env("VM_FLOATING_IP")),
        "admin_cidr": require_env("VM_ADMIN_CIDR"),
    }


def add_base_vm(vm_name: str, vm_spec: dict) -> None:
    path = ROOT / "vm-requests.yaml"
    data = load_yaml(path, {"vms": {}})

    if "vms" not in data or data["vms"] is None:
        data["vms"] = {}

    data["vms"][vm_name] = vm_spec
    save_yaml(path, data)


def ensure_cluster_yaml(cluster: str) -> None:
    path = ROOT / "Kubernetes" / cluster / "cluster.yaml"

    if path.exists():
        return

    data = {
        "cluster": {
            "name": cluster,
            "pod_cidr": "172.16.0.0/16",
            "service_cidr": "10.96.0.0/12",
            "cilium": {
                "ipam_mode": "cluster-pool",
                "cluster_pool_ipv4_pod_cidr_list": "172.16.0.0/16",
                "cluster_pool_ipv4_mask_size": 24,
            },
        }
    }

    save_yaml(path, data)


def add_kubernetes_control_plane(cluster: str, vm_name: str, vm_spec: dict) -> None:
    path = ROOT / "Kubernetes" / cluster / "control-plane-requests.yaml"
    data = load_yaml(path, {"control_planes": {}})

    if "control_planes" not in data or data["control_planes"] is None:
        data["control_planes"] = {}

    data["control_planes"][vm_name] = vm_spec
    save_yaml(path, data)


def add_kubernetes_worker(cluster: str, vm_name: str, vm_spec: dict) -> None:
    path = ROOT / "Kubernetes" / cluster / "worker-node-requests.yaml"
    data = load_yaml(path, {"workers": {}})

    if "workers" not in data or data["workers"] is None:
        data["workers"] = {}

    data["workers"][vm_name] = vm_spec
    save_yaml(path, data)


def main() -> None:
    vm_type = require_env("VM_TYPE")
    vm_name = require_env("VM_NAME")
    vm_spec = build_vm_spec()

    if vm_type == "base":
        add_base_vm(vm_name, vm_spec)
        return

    cluster = require_env("K8S_CLUSTER")
    ensure_cluster_yaml(cluster)

    if vm_type == "kubernetes-control-plane":
        add_kubernetes_control_plane(cluster, vm_name, vm_spec)
        return

    if vm_type == "kubernetes-worker":
        add_kubernetes_worker(cluster, vm_name, vm_spec)
        return

    raise SystemExit(
        "Unsupported VM_TYPE. Expected one of: "
        "base, kubernetes-control-plane, kubernetes-worker"
    )


if __name__ == "__main__":
    main()