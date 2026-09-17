# Verified GitHub Actions pins

The following official action release tags were resolved through GitHub's repository API on 2026-09-17. Both workflows use full commit hashes. This records provenance, not an audit of every action dependency.

| Action | Release | Commit |
|---|---|---|
| actions/checkout | v7.0.1 | 3d3c42e5aac5ba805825da76410c181273ba90b1 |
| actions/setup-python | v7.0.0 | 5fda3b95a4ea91299a34e894583c3862153e4b97 |
| actions/setup-node | v7.0.0 | 820762786026740c76f36085b0efc47a31fe5020 |
| actions/upload-artifact | v7.0.1 | 043fb46d1a93c77aae656e7c1c64a875d1fc6a0a |
| actions/configure-pages | v6.0.0 | 45bfe0192ca1faeb007ade9deae92b16b8254a0d |
| actions/upload-pages-artifact | v5.0.0 | fc324d3547104276b827a68afc52ff2a11cc49c9 |
| actions/deploy-pages | v5.0.1 | 368f82528645a54fb793d4d04e342629a3f51346 |

References: [Python setup](https://github.com/actions/setup-python), [Pages artifact](https://github.com/actions/upload-pages-artifact), [Pages deployment](https://github.com/actions/deploy-pages). Updating a pin should include checking the official release notes, permissions/runtime requirements, tests and a successful deployment. Current workflows target GitHub-hosted ubuntu-latest runners.
