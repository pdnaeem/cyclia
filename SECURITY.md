# Security policy

## Supported versions

Security fixes are made for the latest release. Installed copies of Cyclia update themselves, so keep automatic
updates on.

## How Cyclia handles your data

- Projects and databases are stored on your computer only.
- The calculation engine listens on 127.0.0.1 and accepts only requests that carry the session token of the
  running app.
- Cyclia connects to the internet only to download ecoinvent with your login and to check for updates.
- Your ecoinvent password is passed to ecoinvent's login service and is not stored by Cyclia.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Write to **support@niellosoft.com** with the subject
"Security", a description of the problem, the steps to reproduce it and the Cyclia version.

You will receive an answer within seven days. Once a fix is released, the report is credited in the release
notes unless you prefer otherwise.
