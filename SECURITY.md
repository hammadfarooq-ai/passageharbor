# Security policy

## Scope

PassageHarbor is intended for a single local user. It has no authentication or hardened public-hosting layer. The current `main` branch is the maintained development line; no security support commitment is made for historical snapshots or arbitrary dependency combinations.

Read the [privacy and security guide](docs/privacy-and-security.md) for data flow, local storage, provider transmission, and prompt-injection limitations. A valid citation label is not a proof that an answer is supported.

## Report privately

Use the repository's **Security → Report a vulnerability** option when private vulnerability reporting is enabled. If that option is unavailable, contact the maintainer privately through an appropriate contact channel on the [maintainer's GitHub profile](https://github.com/hammadfarooq-ai). Do not publish exploit details, credentials, private PDFs, or raw database contents in an issue.

Include affected code/version, a safe minimal reproduction using synthetic data, impact, and any relevant environment details. No response-time SLA or bug bounty is promised.

## Exposed credentials

Revoke or rotate an exposed Groq key immediately in the provider console. Update `.env` and restart the app. Removing a key from the working file is insufficient if it entered Git history, logs, issues, or screenshots. Never send a real key as part of a vulnerability report.
