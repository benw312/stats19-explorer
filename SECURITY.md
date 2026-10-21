# Security policy

## Reporting a vulnerability

Please don't open a public issue for a security problem. Report it privately through GitHub instead: on the repository's **Security** tab, choose **Report a vulnerability**. Only the maintainer can see the report.

Please include what you found, how to reproduce it, and what an attacker could do with it. You should get a reply within a week.

## Scope

This is a personal project. It runs as one Docker Compose stack on a home server, with remote access behind Cloudflare Access. Reports about the code in this repository are welcome, for example:

- authentication bypass of the origin check (`stats19.api.access`);
- SQL injection or other injection through the API's filters;
- ways to read or change saved schemes or feedback without access;
- secrets or personal data committed by mistake.

All the collision, traffic and geography data is public open data, so exposing it isn't a vulnerability in itself.
