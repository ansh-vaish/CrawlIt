from pathlib import Path
from urllib.parse import urlparse
import subprocess
import requests
import re

REPOS_DIR = Path("backend/repos")


def parse_repository_info(repo_url: str):
    repo_url = repo_url.strip()

    if not repo_url:
        raise ValueError("Repository URL is required.")

    # SSH
    ssh = re.match(r"^git@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if ssh:
        return ssh.group(1), ssh.group(2)

    if not re.match(r"^[a-zA-Z][a-zA-Z\d+.-]*:", repo_url):
        repo_url = "https://" + repo_url

    try:
        parsed = urlparse(repo_url)
    except Exception:
        raise ValueError("Invalid repository URL.")

    parts = parsed.path.strip("/").split("/")

    if len(parts) < 2:
        raise ValueError("Invalid repository URL.")

    owner = parts[0]
    repo = parts[1].removesuffix(".git")

    return owner, repo


def get_remote_url(repo_url: str):
    repo_url = repo_url.strip()

    if repo_url.startswith("git@"):
        return repo_url

    if re.match(r"^[a-zA-Z][a-zA-Z\d+.-]*:", repo_url):
        return repo_url

    return "https://" + repo_url


def verify_repository(owner: str, repo: str):
    url = f"https://api.github.com/repos/{owner}/{repo}"

    r = requests.get(url)

    if r.status_code == 404:
        raise Exception("Repository not found.")

    if not r.ok:
        raise Exception("Unable to verify repository.")

    data = r.json()

    if data["private"]:
        raise Exception("Private repositories are not supported.")


def clone_repo(repo_url: str):
    owner, repo = parse_repository_info(repo_url)

    verify_repository(owner, repo)

    remote_url = get_remote_url(repo_url)

    clone_path = REPOS_DIR / owner / repo
    clone_path.parent.mkdir(parents=True, exist_ok=True)

    if (clone_path / ".git").exists():
        print("Repository already cloned.")
        return clone_path

    subprocess.run(
        ["git", "ls-remote", "--heads", remote_url],
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            remote_url,
            str(clone_path),
        ],
        check=True,
    )

    return clone_path