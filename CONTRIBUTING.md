# Contributing to LEDGEIT

Full workflow with copy-paste commands: [`docs/team/CHAITANYA.md` §14](docs/team/CHAITANYA.md#14-git-workflow).

## Short version
1. `git switch main && git pull origin main`
2. `git switch -c <name>/<type>/<short-desc>` — types: `feat fix chore docs test refactor`
3. Small commits, [Conventional Commits](https://www.conventionalcommits.org/):
   `feat(proof-core): add Merkle proofs` — scopes: `api web ai sim worker proof-core contracts infra docs tamper`
4. `make test` must pass locally.
5. Push and open a PR using the template. 1 approval from someone other than the author + green CI.
6. Never force-push `main`. Never commit `.env`, keys, weights or dataset images.

## Integrity changes
Anything that changes how bytes are hashed/signed goes through `packages/proof-core/SPEC.md` first,
then `test-vectors/`, then both implementations. CI runs both against the same vectors.
