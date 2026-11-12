# Safe Job Check

Paste a job post or recruiter message and see the common warning signs it contains.
The rules are plain JavaScript in `checks.js`. No server, build step or extra packages are needed.

## Run

Open `index.html` in any browser: double-click the file, or drag it into a browser window.
Everything runs on your own machine. The text you paste is not sent anywhere and nothing is saved.

Paste the full post, including any application instructions, then select **Check job post**.
The page shows a verdict, the number of warning signs, and each sign it found with why it matters and what to do next.

- 0 warnings: No warnings found
- 1 or 2 warnings: Be careful
- 3 or more warnings: High risk

Changing the text hides the old results until you check again. **Clear text** empties the box and resets the page.

## Tests

Use Node.js 18 or newer. Run this command from `projects/safe_job_check`.

```bash
node --test checks.test.js
```

The 120 tests are offline and need no packages. They run each rule against risky and clean sample text, check that `checks.js` also works as a plain browser script, and check the displayed verdicts, blank submissions, and result reset behavior.

## Hints, not proof

The rules match patterns in wording. A warning is a reason to look closer, not proof that a job is a scam, and "No warnings found" does not mean a job is genuine. Verify the employer through its official website before sending money or personal information.
