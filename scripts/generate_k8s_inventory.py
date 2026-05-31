#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


ROOT = Path.cwd()


def run_json(command: list[str]) -> Any:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return json.loads(result.stdout)


def load_yaml(path: Path, default: dict) -> dict:
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data if data is not None else default


def get_server(name: str) -> dict:
    return run_json(["openstack", "server", "show", name, "-f", "json"])


def get_floating_ips() -> list[dict]:
    return run_json(["openstack", "floating", "ip", "list", "-f", "json"])


def extract_ips_from_addresses(addresses: str, network_name: str) -> list[str]:
    for network_block in addresses.split(";"):
        network_block = network_block.strip()

        if not network_block.startswith(f"{network_name}="):
            continue

        raw = network_block.split("=", 1)[1]
        return [ip.strip() for ip in raw.split(",") if ip.strip()]

    return []


def is_private_openstack_ip(ip: str) -> bool:
    return ip.startswith("10.")


def extract_private_ip(server: dict, network_name: str) -> str:
    addresses = server.get("addresses", "")

    if not isinstance(addresses, str):
        raise SystemExit(f"Unexpected addresses format for server {server.get('name')}")

    ips = extract_ips_from_addresses(addresses, network_name)

    for ip in ips:
        if is_private_openstack_ip(ip):
            return ip

    if ips:
        return ips[0]

    raise SystemExit(f"Could not extract private IP for server {server.get('name')}")


def get_server_port_id(server: dict) -> str:
    server_id = server.get("id") or server.get("ID")

    if not server_id:
        raise SystemExit(f"Could not get server id for {server}")

    ports = run_json(["openstack", "port", "list", "--server", server_id, "-f", "json"])

    if not ports:
        raise SystemExit(f"No ports found for server {server.get('name')}")

    if len(ports) > 1:
        raise SystemExit(
            f"Expected exactly one port for server {server.get('name')}, found {len(ports)}"
        )

    return ports[0]["ID"]


def get_floating_ip_for_server(server: dict, floating_ips: list[dict]) -> str:
    port_id = get_server_port_id(server)

    for fip in floating_ips:
        if fip.get("Port") == port_id:
            return fip["Floating IP Address"]

    # Fallback: parse addresses and pick non-10.* IPv4.
    addresses = server.get("addresses", "")
    if isinstance(addresses, str):
        ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", addresses)
        for ip in ips:
            if not is_private_openstack_ip(ip):
                return ip

    raise SystemExit(f"No floating IP associated with server {server.get('name')}")


def load_cluster_requests(cluster: str) -> tuple[dict, dict, dict]:
    cluster_dir = ROOT / "Kubernetes" / cluster

    cluster_config = load_yaml(cluster_dir / "cluster.yaml", {"cluster": {}})
    control_plane_data = load_yaml(
        cluster_dir / "control-plane-requests.yaml",
        {"control_planes": {}},
    )
    worker_data = load_yaml(
        cluster_dir / "worker-node-requests.yaml",
        {"workers": {}},
    )

    control_planes = control_plane_data.get("control_planes") or {}
    workers = worker_data.get("workers") or {}

    if not control_planes:
        raise SystemExit(f"No control planes found for cluster {cluster}")

    return cluster_config, control_planes, workers


def build_host_line(
    name: str,
    spec: dict,
    floating_ips: list[dict],
    include_k8s_vars: bool,
) -> str:
    server = get_server(name)

    network_name = spec.get("network", "private")
    private_ip = extract_private_ip(server, network_name)
    floating_ip = get_floating_ip_for_server(server, floating_ips)

    if include_k8s_vars:
        return (
            f"{name} "
            f"ansible_host={floating_ip} "
            f"k8s_private_ip={private_ip} "
            f"k8s_api_endpoint={private_ip}"
        )

    return f"{name} ansible_host={floating_ip}"


def write_inventory(
    cluster: str,
    control_plane_lines: list[str],
    worker_lines: list[str],
) -> Path:
    inventory_dir = ROOT / "ansible" / "kubernetes" / "inventory"
    inventory_dir.mkdir(parents=True, exist_ok=True)

    path = inventory_dir / f"{cluster}.ini"

    content = []
    content.append("[control_plane]")
    content.extend(control_plane_lines)
    content.append("")

    content.append("[workers]")
    content.extend(worker_lines)
    content.append("")

    content.append("[kubernetes:children]")
    content.append("control_plane")
    content.append("workers")
    content.append("")

    content.append("[kubernetes:vars]")
    content.append("ansible_user=ubuntu")
    content.append("ansible_ssh_private_key_file=/home/gitlab-runner/.ssh/openstack_default_key")
    content.append("ansible_python_interpreter=/usr/bin/python3")
    content.append("ansible_ssh_common_args='-o StrictHostKeyChecking=accept-new'")
    content.append("")

    path.write_text("\n".join(content), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--target-worker", default="")
    args = parser.parse_args()

    _, control_planes, workers = load_cluster_requests(args.cluster)

    if args.target_worker and args.target_worker not in workers:
        raise SystemExit(
            f"Target worker {args.target_worker} is not present in "
            f"Kubernetes/{args.cluster}/worker-node-requests.yaml"
        )

    floating_ips = get_floating_ips()

    control_plane_lines = [
        build_host_line(
            name=name,
            spec=spec,
            floating_ips=floating_ips,
            include_k8s_vars=True,
        )
        for name, spec in control_planes.items()
    ]

    selected_workers = workers

    if args.target_worker:
        selected_workers = {args.target_worker: workers[args.target_worker]}

    worker_lines = [
        build_host_line(
            name=name,
            spec=spec,
            floating_ips=floating_ips,
            include_k8s_vars=False,
        )
        for name, spec in selected_workers.items()
    ]

    inventory_path = write_inventory(args.cluster, control_plane_lines, worker_lines)
    print(f"Wrote inventory: {inventory_path}")


if __name__ == "__main__":
    main()