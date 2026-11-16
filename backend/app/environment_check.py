"""Read-only execution-environment checks; never change OS or sandbox permissions."""

import argparse
import csv
import io
import json
import os
import re
import socket
import subprocess


def classify_docker(returncode, output):
    text = output.lower()
    if returncode == 0:
        return {"status": "accessible"}
    if any(
        word in text
        for word in ("permission denied", "access is denied", "access denied")
    ):
        return {
            "status": "permission_denied",
            "message": "Docker access is denied to this process.",
        }
    if any(word in text for word in ("cannot find", "not found", "is not running")):
        return {
            "status": "not_running",
            "message": "Start Docker Desktop and wait for its engine.",
        }
    return {
        "status": "unavailable",
        "message": "Docker is unavailable to this process.",
    }


def docker_status():
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return classify_docker(result.returncode, result.stdout + result.stderr)
    except FileNotFoundError:
        return {"status": "not_installed", "message": "Docker CLI is not on PATH."}
    except PermissionError:
        return {"status": "permission_denied", "message": "Docker execution is denied."}
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable", "message": "Docker check failed or timed out."}


def windows_token():
    if os.name != "nt":
        return {"integrity": "not_windows"}
    try:
        result = subprocess.run(
            ["whoami", "/groups", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Emit only the integrity level, never user/email/group identifiers.
        for row in csv.reader(io.StringIO(result.stdout)):
            for cell in row:
                match = re.fullmatch(r"S-1-16-(\d+)", cell.strip())
                if match:
                    level = int(match.group(1))
                    return {
                        "integrity": (
                            "low"
                            if level < 8192
                            else "medium"
                            if level < 12288
                            else "high"
                        )
                    }
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"integrity": "unknown"}


def loopback_status(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(1)
            connection.connect(("127.0.0.1", port))
        return {"status": "accessible"}
    except OSError as error:
        code = getattr(error, "winerror", None) or error.errno
        if code in {13, 10013}:
            return {"status": "permission_denied"}
        if code in {61, 111, 10061}:
            return {"status": "not_listening"}
        return {"status": "unavailable"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-docker", action="store_true")
    args = parser.parse_args()
    docker = docker_status()
    loopback = {str(port): loopback_status(port) for port in (5433, 8000, 5173)}
    report = {"process": windows_token(), "docker": docker, "localhost": loopback}
    denied = docker["status"] == "permission_denied" or any(
        item["status"] == "permission_denied" for item in loopback.values()
    )
    if denied:
        report["interpretation"] = (
            "Access is denied to this process. Compare the same command in a normal "
            "terminal; a project code change cannot grant session permissions."
        )
    else:
        report["interpretation"] = (
            "No explicit denial detected; stopped services may still need starting."
        )
    print(json.dumps(report, indent=2))
    return int(denied or (args.require_docker and docker["status"] != "accessible"))


if __name__ == "__main__":
    raise SystemExit(main())
