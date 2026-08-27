# 🔍 GitHub Search & Ranking Engine

A powerful command-line tool and Interactive Terminal UI (TUI) to search, filter, and rank GitHub repositories using a sophisticated, explainable scoring algorithm. 

No more sorting by raw stars; this engine evaluates repositories based on **real relevance** and **code quality**.

---

## ✨ Features

- **Dual Modes**: 
  - 🖥️ **Interactive TUI**: A beautiful terminal application with menus, settings, and interactive result explorers.
  - ⌨️ **CLI Mode**: Fast commands with parameters for scripting, pipelines, or automation.
- **Ranking Engine**:
  - Separates **Relevance** (70% weight: name, description, topic keywords) and **Quality** (30% weight: log-scale stars, push recency, active vs archived state).
  - Matches exact word boundaries using regular expressions (prevents false positives).
- **Fast Local Caching**: Caches search results locally for 1 hour to prevent hitting GitHub API rate limits.
- **Robust Rate Limit Tolerance**: Automatically decodes rate limit reset headers and handles missing tokens gracefully.
- **Machine-Readable output**: Support for `--json` outputs to feed other scripts or API consumers.

---

## 🚀 Quick Start

### 1. Installation

Ensure you have Python 3.8+ installed. Install dependencies:

```bash
pip install rich python-dotenv
```

### 2. Basic Usage

#### Interactive Mode (TUI)
Simply run the script with no arguments to launch the interactive terminal explorer:

```bash
python github_search.py
```

#### CLI Mode
Run a quick search directly from your shell:

```bash
# Basic search
python github_search.py "llm client"

# Search with filters and score explanations
python github_search.py "local llm" --limit 5 --min-stars 100 --explain

# Get JSON output for automation
python github_search.py "agent" --language python --json
```

#### Example Output

Running `python github_search.py "news" --limit 5` will display:

```text
┌─────┬───────────────────────────┬──────────┬─────────────┬────────────┬──────────────┬──────┬───────────────────────┐
│   # │ Repository                │    Stars │ Match Score │ Status     │ Last Push    │ URL  │ Description           │
├─────┼───────────────────────────┼──────────┼─────────────┼────────────┼──────────────┼──────┼───────────────────────┤
│   1 │ georgringer/              │      285 │       28.07 │ Active     │ 2026-08-18   │ Link │ TYPO3 Extension news  │
│     │ news                      │          │             │            │              │      │                       │
├─────┼───────────────────────────┼──────────┼─────────────┼────────────┼──────────────┼──────┼───────────────────────┤
│   2 │ Wscats/                   │      363 │       26.34 │ Active     │ 2026-03-31   │ Link │ 🐼Based on            │
│     │ news                      │          │             │            │              │      │ angular.js, weui and  │
│     │                           │          │             │            │              │      │ node.js rewrite news  │
│     │                           │          │             │            │              │      │ client - 新闻客户端   │
├─────┼───────────────────────────┼──────────┼─────────────┼────────────┼──────────────┼──────┼───────────────────────┤
│   3 │ nextcloud/                │      995 │        23.7 │ Active     │ 2026-08-26   │ Link │ 📰 RSS/Atom feed      │
│     │ news                      │          │             │            │              │      │ reader                │
├─────┼───────────────────────────┼──────────┼─────────────┼────────────┼──────────────┼──────┼───────────────────────┤
│   4 │ Polymer/                  │      265 │       18.75 │ Active     │ 2026-06-20   │ Link │ Polymer News          │
│     │ news                      │          │             │            │              │      │ (Progress Web App     │
│     │                           │          │             │            │              │      │ Template)             │
├─────┼───────────────────────────┼──────────┼─────────────┼────────────┼──────────────┼──────┼───────────────────────┤
│   5 │ zkeq/                     │      169 │       18.74 │ Active     │ 2023-09-15   │ Link │ 前后端均基于 vercel   │
│     │ news                      │          │             │            │              │      │ 的轻量级每日早报项目… │
│     │                           │          │             │            │              │      │ FastAPI +             │
│     │                           │          │             │            │              │      │ BeautifulSoup 实现。  │
└─────┴───────────────────────────┴──────────┴─────────────┴────────────┴──────────────┴──────┴───────────────────────┘
```

---

## 🛠️ CLI Arguments

| Argument | Type | Description |
|:---|:---|:---|
| `query` | positional | The search terms (e.g. `chatgpt api`). |
| `--limit` | integer | Max number of results to display (default: `10`). |
| `--min-stars` | integer | Minimum star count filter (default: `0`). |
| `--language` | string | Filter results by programming language (e.g. `python`, `rust`). |
| `--explain` | flag | Print step-by-step scoring breakdowns for each repo. |
| `--json` | flag | Output raw search data as structured JSON. |

---

## 🧮 How the Score (Match Score) Works

The engine calculates a score between 0 and 100+ for each candidate repository:

$$\text{Final Score} = (\text{Relevance Score} \times 0.7) + (\text{Quality Score} \times 0.3)$$

1. **Relevance Score (70%)**:
   - Searches repository name, description, and topics.
   - Core terms are weighted heavily, while generic stop-words (e.g. *api*, *sdk*, *tool*) receive lighter weights.
2. **Quality Score (30%)**:
   - **Stars**: Evaluated logarithmically to ensure high-star repos don't overpower young, highly active ones.
   - **Activity**: Repos pushed to within 7 days get $+10$ points; repos inactive for over 1 year get $-5$ points.
   - **Archive Penalty**: Archived repositories are penalized by $-10$ points.

---

## 🔑 Speed & Rate Limits (Recommended)

By default, GitHub limits anonymous search requests. To get **higher rate limits**, generate a [Personal Access Token](https://github.com/settings/tokens/new?description=GitHub%20Search%20Engine&scopes=public_repo) (no scopes needed for public queries, `public_repo` for private if needed) and set it in a `.env` file in the same directory:

```env
GITHUB_TOKEN=your_personal_access_token_here
```

*Note: The script also automatically detects active tokens from your GitHub CLI (`gh auth token`) setup.*

---

## 🗄️ Caching

Results are cached locally under `~/.cache/github-search` to keep searches instant and protect API usage. You can clear the cache using the TUI menu options.
