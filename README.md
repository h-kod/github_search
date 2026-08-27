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

Running `python github_search.py` and typing `news` will display:

```text
Search query: news
#   Repo                      Stars   Match Score  Status  Last Push   Link
--  ------------------------  ------  -----------  ------  ----------  -------------------------------------------
1   georgringer/news          285     28.07        Active  2026-08-18  https://github.com/georgringer/news
2   Wscats/news               363     26.34        Active  2026-03-31  https://github.com/Wscats/news
3   nextcloud/news            995     23.7         Active  2026-08-26  https://github.com/nextcloud/news
4   Polymer/news              265     18.75        Active  2026-06-20  https://github.com/Polymer/news
5   zkeq/news                 169     18.74        Active  2023-09-15  https://github.com/zkeq/news
6   codelucas/newspaper       15.144  18.61        Active  2026-08-09  https://github.com/codelucas/newspaper
7   ourongxing/newsnow        21.522  17.8         Active  2026-07-07  https://github.com/ourongxing/newsnow
8   dotnet-architecture/News  1.121   16.43        Active  2023-03-23  https://github.com/dotnet-architecture/News
9   AkshayChordiya/News       843     16.36        Active  2020-11-03  https://github.com/AkshayChordiya/News
10  fhamborg/news-please      2.483   16.34        Active  2026-04-14  https://github.com/fhamborg/news-please
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
