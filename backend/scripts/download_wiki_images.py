# /// script
# dependencies = [
#   "beautifulsoup4",
#   "httpx",
#   "typer",
# ]
# ///

"""Download Fallout Shelter images from The Vault wiki (Fandom).

Uses the MediaWiki API instead of HTML scraping, because Fandom now blocks
plain curl requests to category pages.

Subcommands:
    rooms               Download room images
    weapons             Download weapon images
    apparel             Download apparel/outfit icons
    legendary-dwellers  Download legendary dweller cards + JSON metadata
"""

import json
import re
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

import httpx
import typer
from bs4 import BeautifulSoup

API_URL = "https://fallout-archive.fandom.com/api.php"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Supported legendary dweller names — must match LEGENDARY_DWELLER_IMAGE_FILES
# in app/utils/legendary_dweller_assets.py.  Only entries whose casefolded
# name appears here are kept; everything else is silently dropped.
SUPPORTED_LEGENDARY_NAMES: set[str] = {
    "abraham washington",
    "allistair tenpenny",
    "amata",
    "augustus autumn",
    "bittercup",
    "butch",
    "confessor cromwell",
    "eulogy jones",
    "harkness",
    "james",
    "jericho",
    "lucas simms",
    "madison li",
    "owyn lyons",
    "preston garvey",
    "scribe rothchild",
    "three dog",
}

CATEGORIES = {
    "rooms": "Category:Fallout_Shelter_room_images",
    "weapons": "Category:Fallout_Shelter_weapon_images",
    "apparel": "Category:Fallout_Shelter_apparel_icons",
}


def _api(client: httpx.Client, params: dict) -> dict:
    """Make a GET request to the Fandom MediaWiki API and return JSON."""
    response = client.get(API_URL, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def _is_safe_destination(destination: Path, allowed_parent: Path) -> bool:
    """Return True if destination resolves inside allowed_parent (no path traversal)."""
    try:
        return destination.resolve().is_relative_to(allowed_parent.resolve())
    except (ValueError, OSError):
        return False


def _download(client: httpx.Client, url: str, destination: Path, *, allowed_parent: Path | None = None) -> bool:
    """Download a URL to destination if it doesn't already exist.

    When *allowed_parent* is given, the resolved destination must sit inside
    it — otherwise the download is skipped to prevent path traversal.
    """
    if allowed_parent is not None and not _is_safe_destination(destination, allowed_parent):
        print(f"  skip {destination.name}: path traversal detected")
        return False

    if destination.exists() and destination.stat().st_size > 0:
        print(f"  skip {destination.name}")
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with client.stream("GET", url, timeout=120) as stream:
            stream.raise_for_status()
            with temp.open("wb") as out:
                for chunk in stream.iter_bytes():
                    out.write(chunk)
    except Exception as exc:
        print(f"  fail {destination.name}: {exc}")
        temp.unlink(missing_ok=True)
        return False
    else:
        temp.replace(destination)
        print(f"  got {destination.name}")
        return True


def _category_file_titles(client: httpx.Client, category: str) -> list[str]:
    """List all file titles in a wiki category, following pagination."""
    titles: list[str] = []
    continue_param: dict[str, str] = {}
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmnamespace": "6",
            "cmlimit": "500",
            "format": "json",
        } | continue_param

        data = _api(client, params)
        titles.extend(member["title"] for member in data["query"]["categorymembers"])

        if "continue" not in data:
            break
        continue_param = data["continue"]
    return titles


def _image_info(client: httpx.Client, titles: list[str]) -> dict[str, str]:
    """Map file titles to their full download URLs."""
    urls: dict[str, str] = {}
    for i in range(0, len(titles), 50):
        batch = titles[i : i + 50]
        data = _api(
            client,
            {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json",
            },
        )
        for page in data["query"]["pages"].values():
            if "imageinfo" in page:
                # API normalizes underscores to spaces in titles; use the normalized key.
                urls[page["title"].replace("_", " ")] = page["imageinfo"][0]["url"]
    return urls


def _filename_from_title(title: str) -> str:
    """Strip 'File:' prefix and URL-decode the filename."""
    return unquote(title.removeprefix("File:"))


def _download_category(client: httpx.Client, category: str, download_dir: Path, allowed_exts: tuple[str, ...]) -> int:
    """Download all image files from a wiki category."""
    print(f"Fetching file list from {category}...")
    titles = _category_file_titles(client, category)
    print(f"Found {len(titles)} files")

    urls = _image_info(client, titles)
    downloaded = 0
    resolved_parent = download_dir.resolve()
    for title, url in urls.items():
        filename = _filename_from_title(title)
        if not filename.lower().endswith(allowed_exts):
            continue
        if _download(client, url, download_dir / filename, allowed_parent=resolved_parent):
            downloaded += 1
    print(f"Downloaded {downloaded} new images to {download_dir}")
    return downloaded


def _parse_special(cell_text: str) -> dict[str, int]:
    """Parse the expanded SPECIAL cell text into a dict."""
    keys = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
    digits = re.findall(r"\d+", cell_text)
    return {key: int(digits[i]) for i, key in enumerate(keys) if i < len(digits)}


def _legendary_dwellers(client: httpx.Client) -> list[dict]:
    """Scrape the legendary dweller table from the wiki."""
    data = _api(
        client,
        {
            "action": "parse",
            "page": "Vault dwellers (Fallout Shelter)",
            "prop": "text",
            "format": "json",
        },
    )
    html = data["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "html.parser")

    heading = soup.find(id="List_of_legendary_vault_dwellers")
    if heading is None:
        raise RuntimeError("Could not find legendary dweller heading on wiki page")

    table = heading.find_next("table")
    dwellers: list[dict] = []
    for row in table.find_all("tr")[1:]:  # skip header
        cells = row.find_all(["td", "th"])
        if len(cells) < 4:
            continue

        image_cell = cells[0]
        img_tag = image_cell.find("img")
        image_title = None
        if img_tag:
            # Fandom lazy-loads images; the real URL is usually in data-src.
            src = img_tag.get("data-src") or img_tag.get("src")
            if src and not src.startswith("data:"):
                match = re.search(r"/images/[^/]+/[^/]+/([^/]+)\.(?:png|jpg|jpeg)", src, re.IGNORECASE)
                if match:
                    image_title = f"File:{match.group(1)}.{match.group(0).split('.')[-1]}"

        name_link = cells[1].find("a")
        name = name_link.get_text(strip=True) if name_link else cells[1].get_text(strip=True)
        special = _parse_special(str(cells[2]))
        gear = [a.get_text(strip=True) for a in cells[3].find_all("a")]

        if name and image_title:
            dwellers.append(
                {
                    "name": name,
                    "image_title": image_title,
                    "image_filename": _filename_from_title(image_title),
                    "special": special,
                    "gear": gear,
                }
            )
    return dwellers


app = typer.Typer(help="Download Fallout Shelter images from The Vault wiki.")


@app.command()
def rooms(
    download_dir: Annotated[str, typer.Option("--download-dir")] = "app/static/room_images",
) -> None:
    """Download Fallout Shelter room images."""
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        _download_category(client, CATEGORIES["rooms"], Path(download_dir), (".png", ".jpg", ".jpeg"))


@app.command()
def weapons(
    download_dir: Annotated[str, typer.Option("--download-dir")] = "app/static/weapon_images",
) -> None:
    """Download Fallout Shelter weapon images."""
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        _download_category(client, CATEGORIES["weapons"], Path(download_dir), (".png", ".jpg", ".jpeg"))


@app.command()
def apparel(
    download_dir: Annotated[str, typer.Option("--download-dir")] = "app/static/apparel_images",
) -> None:
    """Download Fallout Shelter apparel/outfit icons."""
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        _download_category(client, CATEGORIES["apparel"], Path(download_dir), (".png", ".jpg", ".jpeg"))


@app.command(name="legendary-dwellers")
def legendary_dwellers(
    download_dir: Annotated[str, typer.Option("--download-dir")] = "app/static/legendary_dweller_images",
    metadata_path: Annotated[str, typer.Option("--metadata")] = "app/data/vault/legendary_dwellers.json",
) -> None:
    """Download legendary dweller cards and write a JSON metadata file."""
    download_path = Path(download_dir)
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        print("Parsing legendary dweller table...")
        all_dwellers = _legendary_dwellers(client)
        print(f"Found {len(all_dwellers)} legendary dwellers on wiki")

        dwellers = [d for d in all_dwellers if d["name"].casefold() in SUPPORTED_LEGENDARY_NAMES]
        print(f"Kept {len(dwellers)} dwellers matching supported roster")

        found_names = {d["name"].casefold() for d in dwellers}
        missing = SUPPORTED_LEGENDARY_NAMES - found_names
        if missing:
            ty.echo(f"Error: supported roster names not found on wiki: {sorted(missing)}", err=True)
            raise ty.Exit(1)

        urls = _image_info(client, [d["image_title"] for d in dwellers])
        downloaded = 0
        resolved_parent = download_path.resolve()
        for dweller in dwellers:
            # MediaWiki normalizes file titles to spaces; match that here.
            url = urls.get(dweller["image_title"].replace("_", " "))
            if not url:
                print(f"  no URL for {dweller['name']}")
                continue
            if _download(client, url, download_path / dweller["image_filename"], allowed_parent=resolved_parent):
                downloaded += 1

    meta_path = Path(metadata_path)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(dwellers, indent=2), encoding="utf-8")
    print(f"Wrote metadata to {meta_path}")
    print(f"Downloaded {downloaded} new legendary dweller images to {download_path}")


@app.command(name="all")
def download_all(
    base_dir: Annotated[str, typer.Option("--base-dir")] = "app/static",
) -> None:
    """Download rooms, weapons, apparel, and legendary dwellers."""
    base = Path(base_dir)
    rooms(str(base / "room_images"))
    weapons(str(base / "weapon_images"))
    apparel(str(base / "apparel_images"))
    legendary_dwellers(
        str(base / "legendary_dweller_images"),
        "app/data/vault/legendary_dwellers.json",
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
