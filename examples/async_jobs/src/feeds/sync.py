"""Fetch two feeds and merge them."""

from feeds import client


async def fetch_all(urls):
    items = []
    for url in urls:
        data = await client.get(url)
        items.extend(data["items"])
    return sorted(items, key=lambda item: item["id"])
