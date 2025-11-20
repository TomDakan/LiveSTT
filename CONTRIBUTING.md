# Contributing to live-stt
Thank you for considering contributing to this project! Please follow these guidelines:
## Setting Up the Development Environment
1.  Fork the repository and clone it locally.
2.  Install `mise` by following the instructions [here](https://mise.jdx.dev/getting-started.html).
3.  Install the project's dependencies by running `mise install`. This will install the correct versions of Python and pdm.
4.  Install the Python packages with `pdm install`.
## Development Workflow
1.  Create a new branch for your feature or bug fix: `git checkout -b my-new-feature`.
2.  Make your changes and ensure that the code adheres to the project's style guidelines.
3.  Run the quality assurance suite to format, lint, and test your changes: `pdm run qa`.
4.  Write tests for any new features or bug fixes and ensure all tests pass: `pdm run test`.
5.  Commit your changes with a descriptive commit message.
6.  Push your branch to your fork: `git push origin my-new-feature`.
7.  Submit a pull request with a clear description of your changes.
## Conventions
*   This project follows the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.
*   Code should be formatted with `ruff`, and type-checked with `mypy`.
*   All new features and bug fixes should be accompanied by tests.
