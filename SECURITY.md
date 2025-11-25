# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability, please follow these steps:

1. **Do NOT open a public GitHub issue.**
2. Email the maintainers at `tomdakan@gmail.com`.
3. Include a description of the vulnerability and steps to reproduce.
4. We will acknowledge receipt within 48 hours.
5. We will provide a fix timeline within 24 hours for critical vulnerabilities.

## Security Measures

- **Secrets**: All API keys and credentials must be stored in `.env` files or Balena secrets, never in code.
- **Scanning**: We use `bandit` and `safety` in our CI pipeline to detect vulnerabilities.
- **Updates**: We automatically update base images and dependencies.
