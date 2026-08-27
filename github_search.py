#!/usr/bin/env python3
"""GitHub repo arama scripti.

Gelişmiş ranking motoru (Relevance vs Quality ayrımı, kelime sınırları, konular,
aktivite skorları), rate limit toleransı, lokal cache ve zengin (interactive rich)
terminal arayüzü desteği sunar.
"""

import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import hashlib
from datetime import datetime, timezone
import argparse

# Opsiyonel kütüphaneler
try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, IntPrompt
    from rich.text import Text
    from rich.align import Align
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False

GITHUB_API = "https://api.github.com/search/repositories"
DEFAULT_LIMIT = 10
POOL_SIZE = 40
CACHE_DIR = os.path.expanduser(os.path.join("~", ".cache", "github-search"))
CACHE_TTL = 3600  # 1 saat (saniye cinsinden)

GENERIC_STOPWORDS = {
    "api", "apis", "wrapper", "wrappers", "unofficial", "official",
    "client", "clients", "sdk", "cli", "tool", "tools", "library",
    "libraries", "lib", "app", "apps", "service", "services", "package",
    "packages", "module", "modules", "project", "free", "open", "source",
    "opensource", "python", "javascript", "typescript", "node", "golang",
}


def get_github_token() -> str:
    """GitHub token'ını sırasıyla ortam değişkeni, .env veya GitHub CLI ayarlarından çeker."""
    # 1. Ortam Değişkeni / .env
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # 2. GitHub CLI (gh) konfigürasyonu
    hosts_path = ""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        hosts_path = os.path.join(appdata, "github-cli", "hosts.yml")
    else:
        hosts_path = os.path.expanduser(os.path.join("~", ".config", "gh", "hosts.yml"))

    if os.path.exists(hosts_path):
        try:
            with open(hosts_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Regex ile yaml içinden oauth_token değerini bulalım
                match = re.search(r"oauth_token:\s*([^\s]+)", content)
                if match:
                    return match.group(1)
        except Exception:
            pass

    return ""


def clean_query_term(term: str) -> str:
    return term.strip().lower()


def get_cache_path(query: str, extra_params: dict) -> str:
    """Sorgu ve parametrelere göre benzersiz bir cache dosya yolu döner."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    param_str = json.dumps(extra_params, sort_keys=True)
    key = f"{query}_{param_str}".encode("utf-8")
    h = hashlib.md5(key).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")


def read_cache(query: str, extra_params: dict) -> dict:
    """Geçerli bir cache varsa içeriğini döner, yoksa None."""
    cache_file = get_cache_path(query, extra_params)
    if os.path.exists(cache_file):
        try:
            stat = os.stat(cache_file)
            age = datetime.now().timestamp() - stat.st_mtime
            if age < CACHE_TTL:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    return None


def write_cache(query: str, extra_params: dict, data: dict):
    """API sonucunu yerel diske cache'ler."""
    cache_file = get_cache_path(query, extra_params)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def clear_all_cache():
    """Tüm cache dosyalarını temizler."""
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            if f.endswith(".json"):
                try:
                    os.remove(os.path.join(CACHE_DIR, f))
                except Exception:
                    pass


def fetch_page(keyword: str, per_page: int, page: int = 1, min_stars: int = 0, language: str = "") -> dict:
    """GitHub REST Search API üzerinden sorgu yapar."""
    # Ekstra parametrelerle cache'lemeyi yönetmek için
    extra_params = {"min_stars": min_stars, "language": language}
    cached = read_cache(keyword, extra_params)
    if cached is not None:
        return cached

    # Query inşası
    q_parts = [keyword]
    if min_stars > 0:
        q_parts.append(f"stars:>={min_stars}")
    if language:
        q_parts.append(f"language:{language}")
    full_q = " ".join(q_parts)

    params = {
        "q": full_q,
        "per_page": per_page,
        "page": page,
    }
    url = f"{GITHUB_API}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-repo-search-script",
    }
    token = get_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
            write_cache(keyword, extra_params, data)
            return data
    except urllib.error.HTTPError as e:
        # Rate limit kontrolleri
        reset_time = e.headers.get("x-ratelimit-reset")
        reset_str = ""
        if reset_time:
            try:
                dt = datetime.fromtimestamp(int(reset_time), tz=timezone.utc).astimezone()
                reset_str = f"Rate limit reset time: {dt.strftime('%H:%M:%S')}"
            except Exception:
                pass

        if RICH_AVAILABLE:
            console.print(Panel(
                f"[bold red]Error: GitHub API returned {e.code} ({e.reason})[/bold red]\n"
                f"{reset_str}\n"
                f"Please define a valid [bold yellow]GITHUB_TOKEN[/bold yellow].",
                title="API Connection Error"
            ))
        else:
            print(f"Error: GitHub API returned {e.code}: {e.reason}")
            if reset_str:
                print(reset_str)
        sys.exit(1)
    except urllib.error.URLError as e:
        if RICH_AVAILABLE:
            console.print(f"[bold red]Network Connection Error:[/bold red] {e.reason}")
        else:
            print(f"Error: Network unreachable: {e.reason}")
        sys.exit(1)


def _terms(keyword: str) -> list:
    return [clean_query_term(w) for w in re.split(r"\W+", keyword) if len(w) >= 3]


def _core_terms(terms: list) -> list:
    core = [t for t in terms if t not in GENERIC_STOPWORDS]
    return core or terms


def _contains_term(text: str, term: str) -> bool:
    """Kelime sınırlarına dikkat ederek kelime araması yapar."""
    if not text:
        return False
    return bool(re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, re.IGNORECASE))


def compute_repo_score(repo: dict, query_terms: list, core_set: set) -> dict:
    """Repo için Relevance ve Quality skorlarını hesaplar."""
    name = repo.get("name", "")
    description = repo.get("description", "") or ""
    topics = repo.get("topics", [])
    stars = repo.get("stargazers_count", 0)
    pushed_at = repo.get("pushed_at", "")
    is_archived = repo.get("archived", False)

    # 1. Relevance Hesaplama
    # Ağırlıklar: Name: 15 (Core), 3 (Generic); Topics: 12 (Core), 2.4 (Generic); Description: 8 (Core), 1.6 (Generic)
    relevance_breakdown = {}
    total_relevance = 0.0

    for term in query_terms:
        is_core = term in core_set
        w_factor = 1.0 if is_core else 0.2
        term_type = "core" if is_core else "generic"

        # Name eşleşmesi
        if _contains_term(name, term):
            score = 15.0 * w_factor
            relevance_breakdown[f"name_match_{term_type}({term})"] = score
            total_relevance += score

        # Topic eşleşmesi
        topic_match = any(_contains_term(t, term) for t in topics)
        if topic_match:
            score = 12.0 * w_factor
            relevance_breakdown[f"topic_match_{term_type}({term})"] = score
            total_relevance += score

        # Description eşleşmesi
        if _contains_term(description, term):
            score = 8.0 * w_factor
            relevance_breakdown[f"desc_match_{term_type}({term})"] = score
            total_relevance += score

    # 2. Quality Hesaplama
    quality_breakdown = {}
    total_quality = 0.0

    # Star Skoru (log scale)
    star_score = math.log10(stars + 1) * 2.0
    quality_breakdown["stars"] = star_score
    total_quality += star_score

    # Aktivite (pushed_at) Skoru
    activity_score = 0.0
    if pushed_at:
        try:
            # ISO 8601 parser basitleştirilmiş
            pushed_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            days_ago = (datetime.now(timezone.utc) - pushed_dt).days
            if days_ago <= 7:
                activity_score = 10.0
            elif days_ago <= 30:
                activity_score = 7.0
            elif days_ago <= 90:
                activity_score = 4.0
            elif days_ago <= 365:
                activity_score = 1.0
            else:
                activity_score = -5.0
        except Exception:
            pass
    quality_breakdown["activity"] = activity_score
    total_quality += activity_score

    # Arşiv cezası
    archive_penalty = -10.0 if is_archived else 0.0
    if is_archived:
        quality_breakdown["archived_penalty"] = archive_penalty
        total_quality += archive_penalty

    # 3. Final Skoru
    # Relevance %70, Quality %30
    final_score = (total_relevance * 0.70) + (total_quality * 0.30)

    return {
        "final_score": round(final_score, 2),
        "relevance": round(total_relevance, 2),
        "quality": round(total_quality, 2),
        "relevance_breakdown": relevance_breakdown,
        "quality_breakdown": quality_breakdown
    }


def search_repos(keyword: str, limit: int = DEFAULT_LIMIT, min_stars: int = 0, language: str = "") -> list:
    """Sorguları işler, birleştirir ve ranking algoritmasına göre sıralar."""
    terms = _terms(keyword)
    if not terms:
        return []

    # Çoklu sorgu inşası
    core = _core_terms(terms)
    queries = [keyword] + core[:5]
    queries = list(dict.fromkeys(queries))  # Deduplicate

    pool_by_id = {}
    for q in queries:
        data = fetch_page(q, per_page=30, min_stars=min_stars, language=language)
        for item in data.get("items", []):
            if item.get("fork"):  # Fork'ları baştan eliyoruz
                continue
            pool_by_id[item["id"]] = item

    core_set = set(core)
    generic_terms_present = any(t not in core_set for t in terms)

    results = []
    for item in pool_by_id.values():
        name = item.get("name", "")
        description = item.get("description", "") or ""

        # Sert Kelime Eşleşme Filtresi (Konu kelimesi mutlaka bulunmalı)
        core_hits = sum(1 for t in core_set if _contains_term(name, t) or _contains_term(description, t))
        if core_set and core_hits == 0:
            continue

        # Jenerik kelime varsa, en az bir tane bulunmalı
        if generic_terms_present:
            generic_hits = sum(1 for t in terms if t not in core_set and (_contains_term(name, t) or _contains_term(description, t)))
            if generic_hits == 0:
                continue

        score_data = compute_repo_score(item, terms, core_set)
        item["_score"] = score_data
        results.append(item)

    # skoruna göre azalan sırada sırala
    results.sort(key=lambda x: x["_score"]["final_score"], reverse=True)
    return results[:limit]


def show_explanation(repo: dict):
    """Repo skorlama detaylarını Panel içinde güzelce basar."""
    score_data = repo["_score"]
    
    if not RICH_AVAILABLE:
        print(f"\nScore Explanation for {repo['full_name']}:")
        print(f"Final Score: {score_data['final_score']}")
        print(f"Relevance Score (70%): {score_data['relevance']}")
        for k, v in score_data['relevance_breakdown'].items():
            print(f"  - {k}: +{v}")
        print(f"Quality Score (30%): {score_data['quality']}")
        for k, v in score_data['quality_breakdown'].items():
            print(f"  - {k}: +{v}")
        return

    exp_text = Text()
    exp_text.append("Final Score Calculation Formula:\n", style="bold cyan")
    exp_text.append("Final Score = (Relevance * 0.70) + (Quality * 0.30)\n\n", style="italic")

    exp_text.append(f"Relevance Score: {score_data['relevance']}\n", style="bold green")
    for k, v in score_data['relevance_breakdown'].items():
        exp_text.append(f"  • {k}: ", style="dim")
        exp_text.append(f"+{v}\n", style="green")

    exp_text.append(f"\nQuality Score: {score_data['quality']}\n", style="bold green")
    for k, v in score_data['quality_breakdown'].items():
        exp_text.append(f"  • {k}: ", style="dim")
        color = "green" if v >= 0 else "red"
        exp_text.append(f"{v:+}\n" if v != 0 else "0\n", style=color)

    exp_text.append(f"\nTotal Weighted Score: {score_data['final_score']}", style="bold yellow underline")

    console.print(Panel(
        exp_text,
        title=f"[bold]{repo['full_name']}[/bold] Score Analysis",
        border_style="yellow"
    ))


def format_date(iso_date: str) -> str:
    return iso_date[:10] if iso_date else "-"


def print_rich_table(items: list):
    """Arama sonuçlarını terminalde tablo olarak basar."""
    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("#", width=3, justify="right")
    table.add_column("Repository", style="cyan", width=25)
    table.add_column("Stars", justify="right", width=8)
    table.add_column("Match Score", justify="right", style="bold yellow")
    table.add_column("Status", width=10)
    table.add_column("Last Push", width=12)
    table.add_column("Description", width=40)

    for i, repo in enumerate(items, 1):
        status = "[red]Archived[/red]" if repo.get("archived") else "[green]Active[/green]"
        table.add_row(
            str(i),
            repo.get("full_name", "-"),
            f"{repo.get('stargazers_count', 0):,}",
            str(repo["_score"]["final_score"]),
            status,
            format_date(repo.get("pushed_at", "")),
            (repo.get("description") or "")[:38] + ("..." if len(repo.get("description") or "") > 38 else "")
        )
    console.print(table)


def interactive_explorer_loop(items: list):
    """Allows user to inspect results and open in browser."""
    if not items:
        return

    while True:
        console.print("\n[bold cyan]Options:[/bold cyan]")
        console.print("  [bold yellow][1-N][/bold yellow] : View repo score analysis")
        console.print("  [bold yellow]o <no>[/bold yellow]: Open in browser (e.g. o 1)")
        console.print("  [bold yellow]n[/bold yellow]     : New Search")
        console.print("  [bold yellow]m[/bold yellow]     : Main Menu")
        console.print("  [bold yellow]q[/bold yellow]     : Exit")

        choice = Prompt.ask("\nYour choice").strip().lower()
        if not choice:
            continue

        if choice == 'q':
            console.print("[bold red]Goodbye![/bold red]")
            sys.exit(0)
        elif choice == 'm':
            return
        elif choice == 'n':
            query = Prompt.ask("\nNew Search Query")
            if query:
                new_items = search_repos(query, DEFAULT_LIMIT)
                if new_items:
                    print_rich_table(new_items)
                    items = new_items
                else:
                    console.print("[bold red]No results found.[/bold red]")
            continue

        # Tarayıcıda açma kontrolü
        open_match = re.match(r"^o\s+(\d+)$", choice)
        if open_match:
            idx = int(open_match.group(1)) - 1
            if 0 <= idx < len(items):
                url = items[idx].get("html_url")
                if url:
                    webbrowser.open(url)
                    console.print(f"[bold green]Opening in browser:[/bold green] {url}")
                else:
                    console.print("[bold red]URL not found.[/bold red]")
            else:
                console.print("[bold red]Invalid selection number.[/bold red]")
            continue

        # Skor detayları kontrolü
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                show_explanation(items[idx])
            else:
                console.print("[bold red]Invalid selection number.[/bold red]")
            continue

        console.print("[bold red]Unknown command.[/bold red]")


def interactive_menu():
    """Tüm aracı yöneten ana interaktif rich menüsü."""
    settings = {
        "limit": DEFAULT_LIMIT,
        "min_stars": 0,
        "language": ""
    }

    while True:
        console.clear()
        console.print(Panel(
            Align.center(
                "[bold magenta]GITHUB SEARCH ENGINE[/bold magenta]\n"
                "[dim]Explainable Repository Ranking Engine & CLI Tool[/dim]"
            ),
            border_style="magenta"
        ))

        console.print("[bold cyan]Main Menu:[/bold cyan]")
        console.print("  [bold yellow]1.[/bold yellow] Search Projects")
        console.print("  [bold yellow]2.[/bold yellow] Search Settings")
        console.print("  [bold yellow]3.[/bold yellow] Clear Cache")
        console.print("  [bold yellow]4.[/bold yellow] Exit")

        choice = Prompt.ask("\nYour choice", choices=["1", "2", "3", "4"], default="1")

        if choice == "1":
            query = Prompt.ask("\nQuery to search")
            if not query:
                continue
            with console.status("[bold green]Scanning GitHub and calculating ranking..."):
                items = search_repos(
                    query, 
                    limit=settings["limit"], 
                    min_stars=settings["min_stars"], 
                    language=settings["language"]
                )
            if items:
                console.print(f"\n[bold green]Ranked top results for '{query}':[/bold green]\n")
                print_rich_table(items)
                interactive_explorer_loop(items)
            else:
                console.print("[bold red]No results found or filters not matched.[/bold red]")
                Prompt.ask("\nPress Enter to continue")

        elif choice == "2":
            console.print("\n[bold cyan]Edit Search Settings:[/bold cyan]")
            settings["limit"] = IntPrompt.ask("Maximum results limit", default=settings["limit"])
            settings["min_stars"] = IntPrompt.ask("Minimum stars", default=settings["min_stars"])
            settings["language"] = Prompt.ask("Programming language filter (can be empty)", default=settings["language"]).strip()
            console.print("[bold green]Settings updated![/bold green]")
            Prompt.ask("\nPress Enter to continue")

        elif choice == "3":
            clear_all_cache()
            console.print("[bold green]Cache cleared successfully![/bold green]")
            Prompt.ask("\nPress Enter to continue")

        elif choice == "4":
            console.print("[bold red]Goodbye![/bold red]")
            sys.exit(0)


def print_simple_table(items: list):
    """Fallback plain console table when rich is not available."""
    if not items:
        print("No results found.")
        return

    headers = ["#", "Repo", "Stars", "Match Score", "Status", "Last Push", "Link"]
    rows = [headers]

    for i, repo in enumerate(items, 1):
        full_name = repo.get("full_name", "-")
        link = repo.get("html_url") or f"https://github.com/{full_name}"
        rows.append([
            str(i),
            full_name,
            f"{repo.get('stargazers_count', 0):,}".replace(",", "."),
            str(repo["_score"]["final_score"]),
            "Archived" if repo.get("archived") else "Active",
            format_date(repo.get("pushed_at", "")),
            link,
        ])

    widths = [max(len(str(row[c])) for row in rows) for c in range(len(headers))]

    def fmt_row(row):
        return "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))

    print(fmt_row(rows[0]))
    print("  ".join("-" * w for w in widths))
    for row in rows[1:]:
        print(fmt_row(row))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="GitHub Search & Ranking Engine")
    parser.add_argument("query", nargs="?", default=None, help="Search query")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum results limit")
    parser.add_argument("--min-stars", type=int, default=0, help="Minimum star filter")
    parser.add_argument("--language", type=str, default="", help="Language filter")
    parser.add_argument("--explain", action="store_true", help="Print detailed score explanation")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON results")

    args = parser.parse_args()

    # Query verilmediyse ve terminal zengin arayüzü destekliyorsa direkt menü aç
    if args.query is None:
        if RICH_AVAILABLE:
            interactive_menu()
        else:
            query = input("Search query: ").strip()
            if not query:
                print("Empty query entered, exiting.")
                sys.exit(1)
            items = search_repos(query, args.limit, args.min_stars, args.language)
            print_simple_table(items)
        return

    # CLI üzerinden arama çalıştırılıyor
    items = search_repos(args.query, args.limit, args.min_stars, args.language)

    if args.json:
        # JSON formatında çıktı
        json_output = {
            "query": args.query,
            "results": [
                {
                    "name": r.get("full_name"),
                    "stars": r.get("stargazers_count"),
                    "score": r["_score"]["final_score"],
                    "relevance": r["_score"]["relevance"],
                    "quality": r["_score"]["quality"],
                    "active": not r.get("archived"),
                    "url": r.get("html_url")
                }
                for r in items
            ]
        }
        print(json.dumps(json_output, indent=2, ensure_ascii=False))
        return

    if not items:
        if RICH_AVAILABLE:
            console.print("[bold red]No results found.[/bold red]")
        else:
            print("No results found.")
        return

    # Normal Tablo çıktısı
    if RICH_AVAILABLE:
        print_rich_table(items)
        if args.explain:
            console.print("\n[bold yellow]Detailed Score Analysis:[/bold yellow]\n")
            for repo in items:
                show_explanation(repo)
    else:
        print_simple_table(items)
        if args.explain:
            print("\nDetailed Score Analysis:\n")
            for repo in items:
                show_explanation(repo)


if __name__ == "__main__":
    main()
