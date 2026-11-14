import os

import yaml


def test_docker_compose_specification():
    compose_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docker-compose.yml",
    )
    assert os.path.exists(compose_path), "docker-compose.yml must exist"

    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    assert "db" in services
    assert "redis" in services
    assert "api" in services
    assert "worker" in services

    # 1. Host Port Hardening
    api_ports = services["api"].get("ports", [])
    assert len(api_ports) == 1
    api_port_str = str(api_ports[0])
    # Must bind loopback only, never 0.0.0.0 or Beszel port 8090
    assert api_port_str.startswith("127.0.0.1:")
    assert "18090" in api_port_str
    assert ":8090:" not in api_port_str
    assert not api_port_str.endswith(":8090")

    # Database and Redis must NOT expose host ports
    assert "ports" not in services["db"]
    assert "ports" not in services["redis"]

    # 2. Resource Limits & Bounded Budgets
    for s_name, service in services.items():
        assert "mem_limit" in service, f"Service {s_name} missing mem_limit"
        assert "cpus" in service, f"Service {s_name} missing cpus"
        assert "security_opt" in service, f"Service {s_name} missing security_opt"
        assert "no-new-privileges:true" in service["security_opt"]

    # 3. Specific suggested budgets
    assert services["db"]["mem_limit"] == "768M"
    assert services["db"]["cpus"] == 0.50

    assert services["redis"]["mem_limit"] == "256M"
    assert services["redis"]["cpus"] == 0.20

    assert services["api"]["mem_limit"] == "512M"
    assert services["api"]["cpus"] == 0.50

    assert services["worker"]["mem_limit"] == "2048M"
    assert services["worker"]["cpus"] == 1.00

    # 4. Storage mount
    api_volumes = services["api"].get("volumes", [])
    worker_volumes = services["worker"].get("volumes", [])
    assert any("/media" in str(v) for v in api_volumes)
    assert any("/media" in str(v) for v in worker_volumes)
