# specs/

This folder holds delta specifications for this change — incremental spec updates that supplement or override the canonical requirements in `docs/requirements/`.

## Usage

- Add one file per requirement or area being specified
- After the change is applied and verified, run `/opsx sync` to merge delta specs back to main specs
- After archive, the canonical requirements in `docs/requirements/` should reflect all decisions made here
