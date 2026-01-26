# /// script
# dependencies = [
#   "beautifulsoup4",
# ]
# ///

import os
import urllib.request
import urllib.parse
import subprocess
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://fallout-archive.fandom.com"
CATEGORY_URL = "/wiki/Category:Fallout_Shelter_room_images"
DOWNLOAD_DIR = "assets/room_images"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def download_image(url, filename):
    path = os.path.join(DOWNLOAD_DIR, filename)
    temp_path = path + ".tmp"

    # Skip if file exists and has content
    if os.path.exists(path):
        file_size = os.path.getsize(path)
        if file_size > 0:
            print(f"Skipping {filename}, already exists ({file_size} bytes).")
            return
        else:
            print(f"Re-downloading {filename}, previous file was empty.")

    try:
        # Download to temporary file first
        subprocess.run(["curl", "-s", url, "-o", temp_path], check=True)

        # Verify download succeeded and has content
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            # Atomic rename
            os.replace(temp_path, path)
            print(f"Downloaded: {filename} ({os.path.getsize(path)} bytes)")
        else:
            print(f"Failed to download {filename}: empty file")
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)


def get_images_from_page(url):
    print(f"Fetching page: {url}")
    try:
        result = subprocess.run(
            ["curl", "-s", url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        html = result.stdout
    except Exception as e:
        print(f"Failed to fetch {url} using curl: {e}")
        return None, 0

    soup = BeautifulSoup(html, "html.parser")
    images_found = 0
    downloaded_urls = set()

    # Fandom/MediaWiki galleries use 'gallerybox' class
    # Recent Fandom category pages might use 'category-page__member'
    items = soup.select(".gallerybox, .category-page__member")
    print(f"Total potential items found: {len(items)}")

    for item in items:
        # Try to find the image link
        # 1. Look for <a> tag with 'image' class or pointing to Wikia
        link_tag = item.select_one("a.image, a.category-page__member-link")
        img_tag = item.find("img")

        img_url = None
        if (
            link_tag
            and link_tag.get("href")
            and "static.wikia.nocookie.net" in link_tag.get("href")
        ):
            img_url = link_tag["href"]
        elif img_tag:
            img_url = img_tag.get("data-src") or img_tag.get("src")
            if img_url and img_url.startswith("data:"):
                img_url = img_tag.get("data-src")

        if not img_url or "static.wikia.nocookie.net" not in img_url:
            continue

        # Clean up the URL to get the full resolution version
        # Remove scaling like /scale-to-width-down/400
        if "/revision/latest" in img_url:
            img_url = img_url.split("/revision/latest")[0] + "/revision/latest"

        if img_url in downloaded_urls:
            continue

        # Determine filename
        filename = None
        if img_tag and img_tag.get("data-image-name"):
            filename = img_tag.get("data-image-name")

        if not filename:
            parts = img_url.split("/")
            if "revision" in parts:
                filename = parts[parts.index("revision") - 1]
            else:
                filename = parts[-1].split("?")[0]

        filename = urllib.parse.unquote(filename)

        # Filter for images and avoid global assets
        if any(
            filename.lower().endswith(ext)
            for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg"]
        ):
            # Skip logos and banners
            if filename.lower() not in [
                "site-logo.png",
                "site-favicon.ico",
                "crossover_banner.jpg",
                "site-background-light",
            ]:
                download_image(img_url, filename)
                downloaded_urls.add(img_url)
                images_found += 1

    # Look for the next page link
    next_page = soup.select_one(
        ".category-page__pagination-next, a.category-page__pagination-next"
    )

    if not next_page:
        # Try finding by text "next page"
        for link in soup.find_all("a"):
            if "next page" in link.text.lower():
                next_page = link
                break

    next_url = None
    if next_page and next_page.get("href"):
        next_url = next_page["href"]
        if not next_url.startswith("http"):
            next_url = BASE_URL + next_url

    return next_url, images_found


def main():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        print(f"Created directory: {DOWNLOAD_DIR}")

    current_url = BASE_URL + CATEGORY_URL
    total_images = 0

    while current_url:
        next_url, count = get_images_from_page(current_url)
        total_images += count
        print(f"Found {count} images on this page.")
        current_url = next_url
        if current_url:
            print(f"Moving to next page: {current_url}")
        else:
            print("No more pages.")

    print(f"Finished! Total images downloaded: {total_images}")


if __name__ == "__main__":
    main()
