# Repository Workflow

- **Discuss before implementing.** For any proposed change, explain the approach and what it will affect. Wait for the user's explicit confirmation before editing files.
- **Commit after successful verification.** Run the relevant tests and review the diff. If verification passes, commit only the approved changes on the current branch. Write the commit message in English and report the test results and commit hash.
- **Report verification blockers.** Fix failures within the approved scope and rerun the checks. If verification still fails or cannot be completed, explain why and leave the changes uncommitted.
- **Keep commits local.** Push, merge, or send Discord messages only when explicitly requested.

## GitHub Releases

See the [maintainer release guide](docs/releasing.md) for the release procedure.

- When asked to prepare a release, create a GitHub Release draft with `python tools/release_draft.py <version> --summary "<release highlight>" --notes-file <path>`. Use the intended commit on `codex/architecture-refactor` in `chzhonge/stock-bot` and confirm it is already pushed.
- Write a short, single-line Traditional Chinese highlight for the title `stock-bot v<version> - <release highlight>`. Write the notes in Traditional Chinese Markdown, comparing the release commit with the previous stable release tag, or with the merge base of upstream `main` and the release branch for the first release. Use `新功能`, `修正`, and `部署與升級` sections as applicable.
- Return the GitHub draft link for review. Let the user publish the draft in GitHub unless they explicitly request publication. Publishing a stable release triggers the Docker image build.
