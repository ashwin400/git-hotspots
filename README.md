# 🔥 Git Hotspot Analyzer

Find where bugs are hiding in your codebase by analyzing git history.

## The Insight

Research shows that:
- **Frequently modified files** are more likely to contain bugs
- **Files touched by many authors** have diffused knowledge (risky!)
- **High code churn** (adding then deleting) indicates design instability
- **Files always changed together** reveal hidden coupling

This tool combines these signals into a **risk score** that tells you where to focus code review, testing, and refactoring efforts.

## Installation

Just Python 3.10+ and Git. No dependencies.

```bash
# Clone or copy
git clone <this-repo>
cd git-hotspots

# Make executable (optional)
chmod +x hotspots.py
```

## Usage

```bash
# Analyze current repo
python3 hotspots.py .

# Analyze specific repo
python3 hotspots.py /path/to/project

# Last 90 days only (recent activity)
python3 hotspots.py . --days 90

# Show more hotspots
python3 hotspots.py . --top 30

# JSON output (for CI/automation)
python3 hotspots.py . --json

# Ignore patterns
python3 hotspots.py . --ignore "*.test.js" "*.spec.ts" "__tests__/*"
```

## Output

```
🔥 GIT HOTSPOT ANALYSIS
   Find where bugs are hiding

   Analyzed 1,234 commits across 156 files
   Date range: 2024-01-15 → 2025-01-28

TOP 15 HOTSPOTS (by risk score):

  Risk   Changes   Authors   Churn  File
──────  ────────  ────────  ──────  ────────────────────────────────────────
    87        45         8    HIGH  src/api/handler.py
    72        38         6     MED  lib/utils.js
    68        33         5    HIGH  core/engine.ts
    ...

🔗 HIDDEN COUPLING (files changed together):

   api/routes.py ↔ db/models.py
   89% correlation (23 co-changes)

   auth/login.js ↔ auth/session.js
   82% correlation (15 co-changes)

📊 SUMMARY

   High risk files: 8
   Medium risk files: 12
   Coupled pairs: 5
   Hottest area: src/api/ (34% of changes)

💡 TIP: Focus code review and testing on high-risk files.
```

## Risk Score Breakdown

| Factor | Weight | What it means |
|--------|--------|---------------|
| Commit frequency | 40% | How often this file changes |
| Author diffusion | 30% | How many different people have touched it |
| Code churn | 30% | Add/delete oscillation (instability) |

## Use Cases

### 1. Onboarding
When joining a new project, run this first. Know where the dragons live.

### 2. Code Review
Prioritize review time on high-risk files. A change to a 90-risk file deserves more scrutiny than a 20-risk file.

### 3. Testing Strategy
High-risk files should have better test coverage. Use this to prioritize test writing.

### 4. Refactoring
Coupled files might need to be merged or have their interface clarified. High-churn files might need redesign.

### 5. CI Integration
Add to your CI pipeline to track risk over time:
```bash
python3 hotspots.py . --json > hotspots.json
# Upload to your metrics dashboard
```

## Ignoring Files

By default, ignores:
- Lock files (`package-lock.json`, `yarn.lock`, etc.)
- Minified files (`*.min.js`, `*.min.css`)
- Binary files
- Build artifacts

Add your own patterns with `--ignore`:
```bash
python3 hotspots.py . --ignore "migrations/*" "generated/*" "vendor/*"
```

## Limitations

- Merge commits are excluded (they skew the data)
- Binary files are excluded (no meaningful line counts)
- Very large repos may take a minute to analyze

## Credits

Inspired by Adam Tornhill's "Your Code as a Crime Scene" and research on software evolution.

## License

MIT
