"""Tests for Docker functionality."""

import os
import subprocess
import time
from pathlib import Path

import pytest


class TestDockerBuild:
    """Test Docker build functionality."""

    def test_dockerfile_exists(self):
        """Test that Dockerfile exists."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile should exist"

    def test_dockerignore_exists(self):
        """Test that .dockerignore exists."""
        dockerignore = Path(__file__).parent.parent / ".dockerignore"
        assert dockerignore.exists(), ".dockerignore should exist"

    def test_docker_compose_exists(self):
        """Test that docker-compose.yml exists."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml should exist"

    def test_env_example_exists(self):
        """Test that .env.example exists."""
        env_example = Path(__file__).parent.parent / ".env.example"
        assert env_example.exists(), ".env.example should exist"


class TestDockerConfiguration:
    """Test Docker configuration files."""

    def test_dockerfile_has_python_base(self):
        """Test that Dockerfile uses Python base image."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        assert "FROM python:" in content, "Dockerfile should use Python base image"
        assert "3.11" in content, "Dockerfile should use Python 3.11"

    def test_dockerfile_exposes_port(self):
        """Test that Dockerfile exposes port 8000."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        assert "EXPOSE 8000" in content, "Dockerfile should expose port 8000"

    def test_dockerfile_has_workdir(self):
        """Test that Dockerfile sets working directory."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        assert "WORKDIR /app" in content, "Dockerfile should set WORKDIR"

    def test_dockerfile_installs_dependencies(self):
        """Test that Dockerfile installs required dependencies."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        assert "iputils-ping" in content, "Dockerfile should install ping utility"
        assert "pip install" in content, "Dockerfile should install Python packages"

    def test_docker_compose_has_services(self):
        """Test that docker-compose.yml defines required services."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()
        assert (
            "collector:" in content
        ), "docker-compose.yml should have collector service"
        assert "webapp:" in content, "docker-compose.yml should have webapp service"

    def test_docker_compose_has_volumes(self):
        """Test that docker-compose.yml defines volumes."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()
        assert "volumes:" in content, "docker-compose.yml should define volumes"
        assert (
            "./data:/app/data" in content
        ), "docker-compose.yml should mount data directory"

    def test_docker_compose_has_port_mapping(self):
        """Test that docker-compose.yml maps ports."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()
        assert "8000:8000" in content, "docker-compose.yml should map port 8000"

    def test_dockerignore_excludes_git(self):
        """Test that .dockerignore excludes .git directory."""
        dockerignore = Path(__file__).parent.parent / ".dockerignore"
        content = dockerignore.read_text()
        assert ".git" in content, ".dockerignore should exclude .git"

    def test_dockerignore_excludes_cache(self):
        """Test that .dockerignore excludes Python cache."""
        dockerignore = Path(__file__).parent.parent / ".dockerignore"
        content = dockerignore.read_text()
        assert "__pycache__" in content, ".dockerignore should exclude __pycache__"

    def test_env_example_has_password_vars(self):
        """Test that .env.example includes password variables."""
        env_example = Path(__file__).parent.parent / ".env.example"
        content = env_example.read_text()
        assert (
            "DEVICEA_PASSWORD" in content
        ), ".env.example should include DEVICEA_PASSWORD"
        assert (
            "DEVICEB_PASSWORD" in content
        ), ".env.example should include DEVICEB_PASSWORD"


@pytest.mark.skipif(
    os.environ.get("SKIP_DOCKER_BUILD_TESTS") == "1",
    reason="Docker build tests skipped (set by SKIP_DOCKER_BUILD_TESTS=1)",
)
class TestDockerBuildProcess:
    """Test actual Docker build process (can be slow, skip in CI if needed)."""

    def test_docker_build_succeeds(self):
        """Test that Docker build completes successfully."""
        project_root = Path(__file__).parent.parent

        # Check if docker is available
        try:
            subprocess.run(
                ["docker", "--version"], check=True, capture_output=True, timeout=5
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            pytest.skip("Docker is not available")

        # Try to build the image
        try:
            result = subprocess.run(
                ["docker", "build", "-t", "nw-watch:test", "."],
                cwd=project_root,
                check=True,
                capture_output=True,
                timeout=180,
            )
            assert result.returncode == 0, "Docker build should succeed"
        except subprocess.TimeoutExpired:
            pytest.fail("Docker build timed out after 180 seconds")
        except subprocess.CalledProcessError as e:
            stderr = (
                e.stderr.decode()
                if e.stderr and isinstance(e.stderr, bytes)
                else str(e.stderr) if e.stderr else "No error output"
            )
            pytest.fail(f"Docker build failed: {stderr}")

    def test_docker_image_has_correct_structure(self):
        """Test that built Docker image has expected structure."""
        # Skip if docker not available
        try:
            subprocess.run(
                ["docker", "--version"], check=True, capture_output=True, timeout=5
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            pytest.skip("Docker is not available")

        # Check if image exists (from previous build)
        try:
            result = subprocess.run(
                ["docker", "images", "-q", "nw-watch:test"],
                check=True,
                capture_output=True,
                timeout=10,
            )
            if not result.stdout.strip():
                pytest.skip("Docker image not built yet")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pytest.skip("Could not check Docker images")

        # Check that the image has expected directories
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "nw-watch:test", "ls", "-la", "/app"],
                check=True,
                capture_output=True,
                timeout=30,
            )
            output = result.stdout.decode()
            assert "collector" in output, "Image should contain collector directory"
            assert "webapp" in output, "Image should contain webapp directory"
            assert "shared" in output, "Image should contain shared directory"
            assert "data" in output, "Image should contain data directory"
        except subprocess.TimeoutExpired:
            pytest.fail("Docker run command timed out")
        except subprocess.CalledProcessError as e:
            stderr = (
                e.stderr.decode()
                if e.stderr and isinstance(e.stderr, bytes)
                else str(e.stderr) if e.stderr else "No error output"
            )
            pytest.fail(f"Docker run failed: {stderr}")


class TestDockerComposeConfiguration:
    """Test docker-compose configuration details."""

    def test_docker_compose_collector_command(self):
        """Test that collector service has correct command."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()
        assert (
            "python -m collector.main" in content
        ), "Collector should run collector.main"
        assert "--config" in content, "Collector should use config file"

    def test_docker_compose_webapp_command(self):
        """Test that webapp service has correct command."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()
        assert "uvicorn webapp.main:app" in content, "Webapp should run via uvicorn"
        assert "--host 0.0.0.0" in content, "Webapp should listen on all interfaces"

    def test_docker_compose_has_restart_policy(self):
        """Test that services have restart policy."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()
        assert "restart:" in content, "Services should have restart policy"

    def test_docker_compose_webapp_depends_on_collector(self):
        """Test that webapp depends on collector."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()
        assert "depends_on:" in content, "Webapp should depend on collector"

    def test_docker_compose_has_network(self):
        """Test that docker-compose defines a network."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()
        assert "networks:" in content, "docker-compose should define networks"
        assert "nw-watch-network" in content, "Should have nw-watch-network"
