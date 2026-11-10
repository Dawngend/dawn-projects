# Profile Builder

Builds a GitHub profile README from `profile.json`. When `github_username` is set, it fetches public repos and sorts them by last push.

## Run

From `projects/profile_builder`, run the generator in an output folder so it does not replace this guide:

```powershell
mkdir output
cd output
python ../build.py ../profile.json
```

The generated file is `output/README.md`. Running directly from `profile_builder` exits with an error to protect this guide. Run from a separate output folder instead. In other folders, the generator creates or replaces `README.md` in the current working directory.

If fetching GitHub repositories fails, the generator exits with a short error and leaves any existing output unchanged. Check `github_username` and your connection, or try again later.

## Tests

From `projects/profile_builder`, run the tests:

```powershell
python -m pip install pytest
python -m pytest -v tests
```

Tests are offline and make no network calls.
