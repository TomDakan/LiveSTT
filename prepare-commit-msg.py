#!/usr/bin/env python
import shutil
import subprocess
import sys
from pathlib import Path
from subprocess import CalledProcessError

try:
    from commitizen.cz.utils import get_backup_file_path
except ImportError as error:
    print("could not import commitizen:")
    print(error)
    exit(1)


def prepare_commit_msg(commit_msg_file: str) -> int:
    """
    Generates a commit message using commitizen if the existing one is invalid.
    """
    # Check if the commit message needs to be generated using commitizen.
    # `cz check` returns a non-zero exit code if the message is not compliant.
    exit_code = subprocess.run(
        [
            "cz",
            "check",
            "--commit-msg-file",
            commit_msg_file,
        ],
        capture_output=True,
    ).returncode
    if exit_code != 0:
        backup_file = Path(get_backup_file_path())
    if backup_file.is_file():
        # Confirm if the commit message from the backup file should be reused.
        answer = input("retry with previous message? [y/N]: ")
    if answer.lower() == "y":
        shutil.copyfile(backup_file, commit_msg_file)
    return 0
    # Use commitizen to generate the commit message interactively.
    try:
        # The `--dry-run` and `--write-message-to-file` flags tell commitizen
        # to write the generated message to our file instead of committing.
        subprocess.run(
            [
                "cz",
                "commit",
                "--dry-run",
                "--write-message-to-file",
                commit_msg_file,
            ],
            stdin=sys.stdin,  # Pass the interactive tty stdin to the subprocess
            stdout=sys.stdout,  # Pass the tty stdout as well
        ).check_returncode()
    except CalledProcessError as error:
        return error.returncode
        # Write the newly generated message to the backup file for future use.
        shutil.copyfile(commit_msg_file, backup_file)
        return 0
    if __name__ == "__main__":
        # This section makes the hook interactive by re-opening the controlling terminal.
        # Git hooks don't always have a direct connection to the user's terminal,
        # so we need to explicitly connect to it.
        # Determine the correct terminal device path based on the operating system.
        if sys.platform == "win32":
            # For Windows, the console device is 'CON'.
            tty_path = "CON"
    else:
        # For Unix-like systems (Linux, macOS), it's '/dev/tty'.
        tty_path = "/dev/tty"
        # Open the terminal for reading and attach it to stdin for the script.
        # This allows the input() and commitizen prompts to be interactive.
        with open(tty_path) as tty:
            sys.stdin = tty
            # Call the main function with the commit message file path provided by Git.
            exit(prepare_commit_msg(sys.argv[1]))
