# git-hotspots

Find where bugs are hiding in your codebase using git history.

Free alternative to CodeScene. Zero dependencies. Works on any git repo.

```bash
python3 hotspots.py /path/to/your/repo
```

---

## The Idea

Files that change frequently are more likely to contain bugs. Files touched by many authors have diffused ownership (nobody fully understands them). Files with high churn (lines added then deleted) signal design instability. This tool combines those signals into a risk score so you know where to focus code review, testing, and refactoring.

## Install

```bash
curl -O https://raw.githubusercontent.com/ashwin400/git-hotspots/main/hotspots.py
python3 hotspots.py .
```

## Usage

```bash
# Analyze current repo
python3 hotspots.py .

# Analyze a specific repo
python3 hotspots.py /path/to/project

# Last 90 days only
python3 hotspots.py . --days 90

# Show top 30 hotspots
python3 hotspots.py . --top 30

# JSON output for CI/dashboards
python3 hotspots.py . --json

# Ignore test files
python3 hotspots.py . --ignore "*.test.js" "*.spec.ts" "__tests__/*"
```

## Example Output

```
git-hotspots: my-api/  (last 180 days, 847 commits)

HOTSPOTS
Rank  Risk    File                            Changes  Authors  Churn
1     98/100  src/auth/middleware.js           142      8        high
2     91/100  src/api/payments-controller.js   89       6        high
3     84/100  src/models/user.js               67       11       medium
4     71/100  src/utils/validation.js          54       4        low
5     68/100  src/routes/api.js                48       7        medium

INSIGHTS
  src/auth/middleware.js  changed 142 times by 8 authors
  High churn suggests repeated design changes. Strong refactor candidate.

  src/api/payments-controller.js  6 authors, no clear owner
  Diffuse ownership increases bug risk. Assign a primary maintainer.

COUPLING (files always changed together)
  user.js + auth/middleware.js  co-changed 67% of the time
  Consider merging or extracting shared logic.
```

## Risk Score Components

| Signal | Weight | Why it matters |
|---|---|---|
| Change frequency | 40% | High-change files have more bug surface |
| Author count | 25% | More authors means diffused ownership |
| Code churn | 25% | Adding then deleting code signals instability |
| Recency | 10% | Recent activity is more relevant than old history |

## Requirements

Python 3.8+. Git must be installed. No other dependencies.
