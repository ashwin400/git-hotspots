#!/usr/bin/env python3
"""
Git Hotspot Analyzer 🔥
Find trouble spots in your codebase by analyzing git history.

Based on research showing that frequently-modified files with many authors
are statistically more likely to contain bugs.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# ANSI colors
class Colors:
    RED = '\033[91m'
    ORANGE = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def color(text: str, c: str) -> str:
    """Wrap text in ANSI color codes."""
    if not sys.stdout.isatty():
        return text
    return f"{c}{text}{Colors.RESET}"


@dataclass
class FileStats:
    """Statistics for a single file."""
    path: str
    commits: int = 0
    authors: set = field(default_factory=set)
    lines_added: int = 0
    lines_deleted: int = 0
    first_commit: Optional[datetime] = None
    last_commit: Optional[datetime] = None
    
    @property
    def author_count(self) -> int:
        return len(self.authors)
    
    @property
    def churn(self) -> float:
        """Churn = min(added, deleted) / max(added, deleted). High churn = instability."""
        total = self.lines_added + self.lines_deleted
        if total == 0:
            return 0.0
        # Churn is when you add and delete roughly equal amounts (oscillation)
        min_val = min(self.lines_added, self.lines_deleted)
        max_val = max(self.lines_added, self.lines_deleted)
        if max_val == 0:
            return 0.0
        return min_val / max_val
    
    @property
    def churn_label(self) -> str:
        if self.churn > 0.7:
            return "HIGH"
        elif self.churn > 0.4:
            return "MED"
        else:
            return "LOW"


@dataclass
class CouplingPair:
    """Two files that are frequently changed together."""
    file1: str
    file2: str
    co_changes: int
    total_changes_1: int
    total_changes_2: int
    
    @property
    def correlation(self) -> float:
        """Percentage of times these files change together."""
        min_changes = min(self.total_changes_1, self.total_changes_2)
        if min_changes == 0:
            return 0.0
        return self.co_changes / min_changes


def run_git(repo_path: str, args: list[str]) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git error: {result.stderr}")
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError("Git not found. Please install git.")


def is_git_repo(path: str) -> bool:
    """Check if path is a git repository."""
    try:
        run_git(path, ['rev-parse', '--git-dir'])
        return True
    except:
        return False


def should_ignore(path: str, patterns: list[str]) -> bool:
    """Check if file should be ignored based on patterns."""
    import fnmatch
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        # Also match just the filename
        if fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    return False


def analyze_repo(
    repo_path: str,
    days: Optional[int] = None,
    ignore_patterns: Optional[list[str]] = None
) -> tuple[dict[str, FileStats], list[CouplingPair], dict]:
    """
    Analyze a git repository and return file statistics.
    
    Returns:
        - Dict of file path -> FileStats
        - List of CouplingPairs
        - Metadata dict (total commits, date range, etc.)
    """
    ignore_patterns = ignore_patterns or []
    
    # Default ignore patterns for common non-code files
    default_ignores = [
        '*.lock', 'package-lock.json', 'yarn.lock', 'Cargo.lock',
        '*.min.js', '*.min.css', '*.map',
        '.gitignore', '.gitattributes',
        '*.svg', '*.png', '*.jpg', '*.gif', '*.ico',
        '*.woff', '*.woff2', '*.ttf', '*.eot',
    ]
    ignore_patterns.extend(default_ignores)
    
    # Build git log command
    log_args = [
        'log',
        '--numstat',
        '--format=COMMIT:%H|%an|%ad',
        '--date=iso-strict',
        '--no-merges',
    ]
    
    if days:
        since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        log_args.append(f'--since={since_date}')
    
    output = run_git(repo_path, log_args)
    
    # Parse the output
    file_stats: dict[str, FileStats] = defaultdict(lambda: FileStats(path=""))
    commit_files: list[set[str]] = []  # For coupling analysis
    current_commit_files: set[str] = set()
    current_author = ""
    current_date = None
    total_commits = 0
    
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('COMMIT:'):
            # Save previous commit's files for coupling analysis
            if current_commit_files:
                commit_files.append(current_commit_files.copy())
                current_commit_files.clear()
            
            # Parse commit header
            parts = line[7:].split('|')
            if len(parts) >= 3:
                current_author = parts[1]
                try:
                    current_date = datetime.fromisoformat(parts[2].replace('Z', '+00:00'))
                except:
                    current_date = None
                total_commits += 1
        else:
            # Parse numstat line: added \t deleted \t filename
            parts = line.split('\t')
            if len(parts) >= 3:
                added, deleted, filepath = parts[0], parts[1], parts[2]
                
                # Skip binary files (shown as -)
                if added == '-' or deleted == '-':
                    continue
                
                # Skip ignored files
                if should_ignore(filepath, ignore_patterns):
                    continue
                
                # Update file stats
                if file_stats[filepath].path == "":
                    file_stats[filepath].path = filepath
                
                stats = file_stats[filepath]
                stats.commits += 1
                stats.authors.add(current_author)
                stats.lines_added += int(added)
                stats.lines_deleted += int(deleted)
                
                if current_date:
                    if stats.first_commit is None or current_date < stats.first_commit:
                        stats.first_commit = current_date
                    if stats.last_commit is None or current_date > stats.last_commit:
                        stats.last_commit = current_date
                
                current_commit_files.add(filepath)
    
    # Don't forget the last commit
    if current_commit_files:
        commit_files.append(current_commit_files)
    
    # Calculate coupling (files changed together)
    co_change_matrix: dict[tuple[str, str], int] = defaultdict(int)
    for files in commit_files:
        files_list = sorted(files)
        for i, f1 in enumerate(files_list):
            for f2 in files_list[i+1:]:
                co_change_matrix[(f1, f2)] += 1
    
    # Build coupling pairs (only significant ones)
    coupling_pairs = []
    for (f1, f2), count in co_change_matrix.items():
        if count >= 3:  # At least 3 co-changes to be significant
            pair = CouplingPair(
                file1=f1,
                file2=f2,
                co_changes=count,
                total_changes_1=file_stats[f1].commits,
                total_changes_2=file_stats[f2].commits
            )
            if pair.correlation >= 0.5:  # At least 50% correlation
                coupling_pairs.append(pair)
    
    # Sort by correlation
    coupling_pairs.sort(key=lambda p: p.correlation, reverse=True)
    
    # Calculate metadata
    all_dates = [s.first_commit for s in file_stats.values() if s.first_commit]
    all_dates += [s.last_commit for s in file_stats.values() if s.last_commit]
    
    metadata = {
        'total_commits': total_commits,
        'total_files': len(file_stats),
        'date_range': {
            'start': min(all_dates).isoformat() if all_dates else None,
            'end': max(all_dates).isoformat() if all_dates else None,
        },
        'days_analyzed': days,
    }
    
    return dict(file_stats), coupling_pairs, metadata


def calculate_risk_score(stats: FileStats, max_commits: int, max_authors: int) -> int:
    """
    Calculate a risk score from 0-100 based on multiple factors.
    
    Factors:
    - Commit frequency (normalized)
    - Author diffusion (many authors = risky)
    - Code churn (high churn = unstable)
    """
    # Normalize commit frequency (0-40 points)
    commit_score = (stats.commits / max_commits) * 40 if max_commits > 0 else 0
    
    # Author diffusion (0-30 points) - more authors = higher risk
    # 1 author = 0, 5+ authors = max
    author_score = min((stats.author_count - 1) / 4, 1.0) * 30
    
    # Churn score (0-30 points)
    churn_score = stats.churn * 30
    
    return min(100, int(commit_score + author_score + churn_score))


def print_report(
    file_stats: dict[str, FileStats],
    coupling_pairs: list[CouplingPair],
    metadata: dict,
    top_n: int = 15,
    show_coupling: bool = True
):
    """Print a formatted report to stdout."""
    if not file_stats:
        print(color("No files found in git history.", Colors.ORANGE))
        return
    
    # Calculate risk scores
    max_commits = max(s.commits for s in file_stats.values())
    max_authors = max(s.author_count for s in file_stats.values())
    
    scored_files = []
    for path, stats in file_stats.items():
        risk = calculate_risk_score(stats, max_commits, max_authors)
        scored_files.append((risk, stats))
    
    scored_files.sort(key=lambda x: x[0], reverse=True)
    
    # Header
    print()
    print(color("🔥 GIT HOTSPOT ANALYSIS", Colors.BOLD))
    print(color("   Find where bugs are hiding", Colors.DIM))
    print()
    
    # Metadata
    commits_str = f"{metadata['total_commits']:,}"
    files_str = f"{metadata['total_files']:,}"
    print(f"   Analyzed {color(commits_str, Colors.CYAN)} commits across {color(files_str, Colors.CYAN)} files")
    
    if metadata['date_range']['start'] and metadata['date_range']['end']:
        start = metadata['date_range']['start'][:10]
        end = metadata['date_range']['end'][:10]
        print(f"   Date range: {start} → {end}")
    
    print()
    
    # Top hotspots
    print(color(f"TOP {min(top_n, len(scored_files))} HOTSPOTS", Colors.BOLD) + color(" (by risk score):", Colors.DIM))
    print()
    
    # Table header
    print(f"{'Risk':>6}  {'Changes':>8}  {'Authors':>8}  {'Churn':>6}  File")
    print(f"{'─'*6}  {'─'*8}  {'─'*8}  {'─'*6}  {'─'*40}")
    
    for risk, stats in scored_files[:top_n]:
        # Color code risk
        if risk >= 70:
            risk_str = color(f"{risk:>6}", Colors.RED)
        elif risk >= 50:
            risk_str = color(f"{risk:>6}", Colors.ORANGE)
        else:
            risk_str = color(f"{risk:>6}", Colors.GREEN)
        
        # Color code churn
        churn_label = stats.churn_label
        if churn_label == "HIGH":
            churn_str = color(f"{churn_label:>6}", Colors.RED)
        elif churn_label == "MED":
            churn_str = color(f"{churn_label:>6}", Colors.ORANGE)
        else:
            churn_str = f"{churn_label:>6}"
        
        # Truncate long paths
        path = stats.path
        if len(path) > 50:
            path = "..." + path[-47:]
        
        print(f"{risk_str}  {stats.commits:>8}  {stats.author_count:>8}  {churn_str}  {path}")
    
    # Coupling analysis
    if show_coupling and coupling_pairs:
        print()
        print(color("🔗 HIDDEN COUPLING", Colors.BOLD) + color(" (files changed together):", Colors.DIM))
        print()
        
        for pair in coupling_pairs[:8]:
            pct = int(pair.correlation * 100)
            
            # Truncate paths
            f1 = pair.file1
            f2 = pair.file2
            if len(f1) > 35:
                f1 = "..." + f1[-32:]
            if len(f2) > 35:
                f2 = "..." + f2[-32:]
            
            print(f"   {f1} ↔ {f2}")
            print(f"   {color(f'{pct}% correlation', Colors.CYAN)} ({pair.co_changes} co-changes)")
            print()
    
    # Summary
    print(color("📊 SUMMARY", Colors.BOLD))
    print()
    
    high_risk = sum(1 for risk, _ in scored_files if risk >= 70)
    med_risk = sum(1 for risk, _ in scored_files if 50 <= risk < 70)
    
    print(f"   {color(f'High risk files:', Colors.RED)} {high_risk}")
    print(f"   {color(f'Medium risk files:', Colors.ORANGE)} {med_risk}")
    print(f"   Coupled pairs: {len(coupling_pairs)}")
    
    # Find most changed directory
    dir_counts = defaultdict(int)
    for stats in file_stats.values():
        dir_path = os.path.dirname(stats.path) or "."
        dir_counts[dir_path] += stats.commits
    
    if dir_counts:
        hottest_dir = max(dir_counts.items(), key=lambda x: x[1])
        total_changes = sum(s.commits for s in file_stats.values())
        pct = int((hottest_dir[1] / total_changes) * 100) if total_changes > 0 else 0
        print(f"   Hottest area: {color(hottest_dir[0], Colors.CYAN)} ({pct}% of changes)")
    
    print()
    print(color("💡 TIP:", Colors.DIM) + " Focus code review and testing on high-risk files.")
    print()


def output_json(
    file_stats: dict[str, FileStats],
    coupling_pairs: list[CouplingPair],
    metadata: dict
):
    """Output results as JSON."""
    max_commits = max((s.commits for s in file_stats.values()), default=1)
    max_authors = max((s.author_count for s in file_stats.values()), default=1)
    
    hotspots = []
    for path, stats in file_stats.items():
        risk = calculate_risk_score(stats, max_commits, max_authors)
        hotspots.append({
            'path': path,
            'risk_score': risk,
            'commits': stats.commits,
            'authors': stats.author_count,
            'lines_added': stats.lines_added,
            'lines_deleted': stats.lines_deleted,
            'churn': round(stats.churn, 3),
            'churn_label': stats.churn_label,
        })
    
    hotspots.sort(key=lambda x: x['risk_score'], reverse=True)
    
    coupling = [
        {
            'file1': p.file1,
            'file2': p.file2,
            'correlation': round(p.correlation, 3),
            'co_changes': p.co_changes,
        }
        for p in coupling_pairs
    ]
    
    result = {
        'metadata': metadata,
        'hotspots': hotspots,
        'coupling': coupling,
    }
    
    print(json.dumps(result, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(
        description='🔥 Git Hotspot Analyzer - Find trouble spots in your codebase',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s .                    Analyze current repo
  %(prog)s /path/to/repo        Analyze specific repo
  %(prog)s . --days 90          Last 90 days only
  %(prog)s . --top 20           Show top 20 hotspots
  %(prog)s . --coupling         Focus on file coupling
  %(prog)s . --json             Output as JSON
  %(prog)s . --ignore "*.test.*" "*.spec.*"  Ignore test files
        """
    )
    
    parser.add_argument('repo', nargs='?', default='.', help='Path to git repository')
    parser.add_argument('--days', '-d', type=int, help='Analyze only last N days')
    parser.add_argument('--top', '-n', type=int, default=15, help='Show top N hotspots (default: 15)')
    parser.add_argument('--coupling', '-c', action='store_true', help='Show coupling analysis')
    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')
    parser.add_argument('--ignore', '-i', nargs='*', default=[], help='File patterns to ignore')
    
    args = parser.parse_args()
    
    # Resolve repo path
    repo_path = os.path.abspath(os.path.expanduser(args.repo))
    
    if not os.path.isdir(repo_path):
        print(f"Error: {repo_path} is not a directory", file=sys.stderr)
        sys.exit(1)
    
    if not is_git_repo(repo_path):
        print(f"Error: {repo_path} is not a git repository", file=sys.stderr)
        sys.exit(1)
    
    try:
        file_stats, coupling_pairs, metadata = analyze_repo(
            repo_path,
            days=args.days,
            ignore_patterns=args.ignore
        )
        
        if args.json:
            output_json(file_stats, coupling_pairs, metadata)
        else:
            print_report(
                file_stats,
                coupling_pairs,
                metadata,
                top_n=args.top,
                show_coupling=args.coupling or True  # Always show coupling by default
            )
    
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)


if __name__ == '__main__':
    main()
