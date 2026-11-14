import json
import re


def parse_tailscale_status_json(status_json_str: str) -> dict:
    """Helper mirroring the python3 one-liner used in tailscale-status.sh."""
    data = json.loads(status_json_str)
    self_info = data.get("Self", {})
    return {
        "backend_state": data.get("BackendState", "Unknown"),
        "hostname": self_info.get("HostName", "Unknown"),
        "dns_name": self_info.get("DNSName", "").rstrip("."),
        "tailscale_ips": self_info.get("TailscaleIPs", []),
    }


def is_already_serving_port(serve_status_text: str, port: int) -> bool:
    """Helper mirroring tailscale-serve-enable.sh port check."""
    pattern = rf"(127\.0\.0\.1|localhost|http://localhost):{port}"
    return bool(re.search(pattern, serve_status_text))


def has_unrelated_serve_active(serve_status_text: str, port: int) -> bool:
    """Helper mirroring tailscale-serve-enable.sh conflict detection."""
    if not serve_status_text.strip() or "no active serve" in serve_status_text.lower():
        return False
    # If active serve does not mention our port, it belongs to another service
    return not is_already_serving_port(serve_status_text, port)


def test_tailscale_status_json_parsing():
    sample_json = json.dumps(
        {
            "BackendState": "Running",
            "Self": {
                "HostName": "home-server",
                "DNSName": "home-server.tailnet123.ts.net.",
                "TailscaleIPs": ["100.101.102.103", "fd7a:115c:a1e0::1"],
            },
        }
    )
    parsed = parse_tailscale_status_json(sample_json)
    assert parsed["backend_state"] == "Running"
    assert parsed["hostname"] == "home-server"
    assert parsed["dns_name"] == "home-server.tailnet123.ts.net"
    assert "100.101.102.103" in parsed["tailscale_ips"]


def test_tailscale_disconnected_daemon_detection():
    sample_stopped = json.dumps(
        {
            "BackendState": "Stopped",
            "Self": {"HostName": "home-server"},
        }
    )
    parsed = parse_tailscale_status_json(sample_stopped)
    assert parsed["backend_state"] != "Running"


def test_serve_idempotency_detection():
    active_serve = """
    https://home-server.tailnet123.ts.net (tailnet only)
    |-- / proxy http://127.0.0.1:18090
    """
    assert is_already_serving_port(active_serve, 18090)
    assert not has_unrelated_serve_active(active_serve, 18090)


def test_unrelated_serve_conflict_refusal():
    # Another container/app (e.g., Immich or Beszel or Nextcloud) is already using Serve
    unrelated_serve = """
    https://home-server.tailnet123.ts.net (tailnet only)
    |-- / proxy http://127.0.0.1:3000
    """
    assert not is_already_serving_port(unrelated_serve, 18090)
    assert has_unrelated_serve_active(unrelated_serve, 18090)


def test_disable_guard_against_modifying_other_services():
    other_serve = """
    https://home-server.tailnet123.ts.net (tailnet only)
    |-- / proxy http://127.0.0.1:8000
    """
    # The disable script must check if 18090 is present before turning off serve
    assert not is_already_serving_port(other_serve, 18090)


def test_tailscale_scripts_contain_no_destructive_commands():
    """Verify scripts strictly uphold invariants and never run dangerous commands."""
    import os

    scripts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "scripts",
    )
    for script_name in (
        "tailscale-status.sh",
        "tailscale-serve-enable.sh",
        "tailscale-serve-disable.sh",
    ):
        script_path = os.path.join(scripts_dir, script_name)
        assert os.path.exists(script_path), f"Script {script_name} must exist"
        with open(script_path, encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            trimmed = line.strip()
            # Ignore comments
            if trimmed.startswith("#") or not trimmed:
                continue
            # Strict safety assertions on executable commands
            assert "tailscale serve reset" not in trimmed, (
                f"{script_name} must NEVER execute 'tailscale serve reset'"
            )
            assert "tailscale down" not in trimmed, (
                f"{script_name} must NEVER execute 'tailscale down'"
            )
            assert "tailscale funnel" not in trimmed, (
                f"{script_name} must NEVER execute 'tailscale funnel'"
            )
