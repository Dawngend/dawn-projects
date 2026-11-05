# Profile Builder

Builds a GitHub profile README from `profile.json`. When `github_username` is set, it fetches public repos and sorts them by last push.

## Run

From `projects/profile_builder`, run the generator in an output folder so it does not replace this guide:

```powershell
mkdir output
cd output
python ../build.py ../profile.json
```

The generated file is `output/README.md`.

## Tests

From `projects/profile_builder`, run the tests:

```powershell
python -m pip install pytest
python -m pytest -v tests
```

Tests are offline and make no network calls.
