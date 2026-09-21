"""Read-only CHIRPS availability, shared by the updater and freshness monitor."""
import requests

if __package__:
    from .fetch_chirps import build_url
else:
    from fetch_chirps import build_url


def is_month_released(year: int, month: int) -> bool:
    """Inspect headers only. A 404 means unreleased; other failures must surface."""
    with requests.head(build_url(year, month), allow_redirects=True, timeout=20) as response:
        if response.status_code == 404:
            return False
        response.raise_for_status()
        if response.status_code != 200:
            raise RuntimeError(f"Unexpected CHIRPS status: {response.status_code}")
        return True


def previous_month(year: int, month: int) -> tuple[int, int]:
    return (year, month - 1) if month > 1 else (year - 1, 12)


def newest_release(ceiling: tuple[int, int], probe=is_month_released) -> tuple[int, int]:
    month = ceiling
    for _ in range(24):
        if probe(*month):
            return month
        month = previous_month(*month)
    raise RuntimeError("No CHIRPS release found within 24 months; availability is unknown")
