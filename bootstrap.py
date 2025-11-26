import json
import os
import platform
import subprocess
import sys
import time

# --- Configuration (from Copier) ---
GITHUB_USER = os.getenv("_GITHUB_USER", "TomDakan")
PROJECT_NAME = os.getenv("_PROJECT_NAME", "live-stt")
DESCRIPTION = os.getenv("_DESCRIPTION", "")
IS_PRIVATE = os.getenv("_IS_PRIVATE", "False") == "True"

RUN_QA_CHECKS = False
PRECOMMIT_INSTALL = "True" == "True"
INITIALIZE_GIT = "True" == "True"
PUSH_TO_GITHUB = "True" == "True"
TASK_TRACKING = os.getenv("_TASK_TRACKING", "GitHub Projects")
REPO_NAME = f"{GITHUB_USER}/{PROJECT_NAME}"


def run_command(
    command: list[str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Runs a command from the project's root directory."""
    print(f"\n> {' '.join(command)}")
    use_shell = platform.system() == "Windows"
    try:
        # Explicitly merge stderr into stdout for reliable capture
        return subprocess.run(
            command,
            check=check,
            shell=use_shell,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        # All output is now in stdout
        print(f"Output: {e.stdout}")
        sys.exit(1)
    except FileNotFoundError:
        print(
            f"Error: Command '{command[0]}' not found. Is it installed and in your PATH?"
        )
        sys.exit(1)


def check_repo_exists(repo_name: str) -> bool:
    """Check if a GitHub repository already exists using 'gh repo view'."""
    print(f"--- Checking if repository '{repo_name}' exists ---")

    # 'gh repo view' will return 0 if the repo exists and non-zero if it doesn't.
    # We set check=False to handle the non-zero exit code ourselves.
    result = subprocess.run(
        ["gh", "repo", "view", repo_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.returncode == 0:
        return True  # Repo exists

    if "Could not resolve to a Repository" in result.stderr:
        return False  # Repo does not exist

    # Handle other errors (like auth failure)
    if "failed to authenticate" in result.stderr.lower():
        print(
            "Warning: 'gh auth status' failed. Proceeding with create attempt...",
            file=sys.stderr,
        )

    return False


def create_github_repo() -> None:
    """Create and push to the GitHub repository."""

    if check_repo_exists(REPO_NAME):
        print(f"GitHub repository '{REPO_NAME}' already exists. Skipping creation.")
        # We still need to set the remote URL for the local repo
        print("--- Setting remote URL ---")
        run_command(["git", "remote", "add", "origin", f"git@github.com:{REPO_NAME}.git"])
        print("--- Pushing to existing repository ---")
    else:
        print(f"--- Creating GitHub repository: {REPO_NAME} ---")

        create_command = [
            "gh",
            "repo",
            "create",
            REPO_NAME,
            f"--description={DESCRIPTION}",
            "--source=.",  # Use the current directory as the source
            "--push",  # Push existing commits to the new repo
        ]

        if IS_PRIVATE:
            create_command.append("--private")
        else:
            create_command.append("--public")

        run_command(create_command)
        print(f"Successfully created and pushed to https://github.com/{REPO_NAME}")

    # This is a good place to set branch protection, etc.
    # print("--- Setting default branch protection ---")
    # run_command(["gh", "repo", "edit", REPO_NAME, "--default-branch=main"])


def create_github_project_board() -> None:
    """Creates a GitHub project board for the repository."""
    print(f"--- Creating GitHub project for {REPO_NAME} ---")
    result = run_command(
        [
            "gh",
            "project",
            "create",
            f"{PROJECT_NAME} Roadmap",
            "--owner",
            GITHUB_USER,
        ]
    )
    project_url = result.stdout.strip()
    print(f"Successfully created GitHub project: {project_url}")

    # Update the ROADMAP.md file
    with open("ROADMAP.md") as f:
        content = f.read()
    content = content.replace("PROJECT_URL_PLACEHOLDER", project_url)
    with open("ROADMAP.md", "w") as f:
        f.write(content)
    print("Updated ROADMAP.md with project URL.")


def check_gh_auth() -> bool:
    """Checks if the user is logged into the correct GitHub account."""
    result = run_command(["gh", "auth", "status"], check=False)
    # Check the stdout stream, which now contains all output
    return GITHUB_USER in result.stdout


def get_workflow_run_id(workflow_name: str) -> str | None:
    """Polls for a workflow run and returns its ID."""
    for _ in range(30):  # Poll for 30 seconds
        result = run_command(["gh", "run", "list", "--json", "databaseId,name"])
        runs = json.loads(result.stdout)
        for run in runs:
            if run.get("name") == workflow_name:
                return str(run["databaseId"])
        print(f"Waiting for '{workflow_name}' action to start...")
        time.sleep(1)
    print(f"Error: Timed out waiting for '{workflow_name}' workflow.")
    return None


def main() -> None:
    """Main execution flow for initial project setup."""

    print("\n--- Installing PDM dependencies ---")
    run_command(["pdm", "install"])

    if RUN_QA_CHECKS:
        print("\n--- Running QA checks ---")
        run_command(["pdm", "run", "qa"])

    if PRECOMMIT_INSTALL:
        print("\n--- Installing pre-commit hooks ---")
        run_command(["pre-commit", "install"])

    if INITIALIZE_GIT:
        print("--- Initializing Git repository ---")
        if not os.path.exists(".git"):
            run_command(["git", "init"])
            run_command(["git", "add", "."])
            run_command(
                ["git", "commit", "-m", "feat: Initial commit from copier template"]
            )
        else:
            print("Git repository already initialized.")

        if PUSH_TO_GITHUB:
            print("--- Checking GitHub Authentication ---")
            if not check_gh_auth():
                print(
                    f"Error: Not logged into GitHub as '{GITHUB_USER}'. "
                    "Please run 'gh auth login'."
                )
                sys.exit(1)
            print("GitHub auth successful.")

            print("\n--- Creating and pushing to GitHub ---")

            create_github_repo()

            if TASK_TRACKING == "GitHub Projects":
                create_github_project_board()

    print("\n--- Bootstrap finished successfully! ---")


if __name__ == "__main__":
    main()
