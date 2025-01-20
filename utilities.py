from bs4 import BeautifulSoup
import requests

def get_latest_release_date(repo_url):
    """
    Fetches the latest release version and release date from a GitHub repository.
    Args:
        repo_url (str): The URL of the GitHub repository.
    Returns:
        tuple: A tuple containing the latest release version (str) and the release date (str in ISO 8601 format).
    Raises:
        Exception: If the releases page cannot be fetched or if no releases or release dates are found.
    """
    # Construct the releases page URL
    releases_url = f"{repo_url}/releases"

    # Send a GET request to the releases page
    response = requests.get(releases_url)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch the releases page: {response.status_code}")

    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the latest release tag (usually it's the first `a` with the class `Link--primary` in the releases list)
    latest_release_tag = soup.find('a', {'class': 'Link--primary'})

    if not latest_release_tag:
        raise Exception("Could not find any releases on the page.")

    # Extract the release version text
    latest_release = latest_release_tag['href'].split('/')[-1]


    # Find the release date (usually it's in a `relative-time` tag within the release tag)
    release_date_tag = soup.find('relative-time')

    if not release_date_tag:
        raise Exception("Could not find the release date on the page.")

    # Extract the release date text
    release_date = release_date_tag['datetime']

    return latest_release, release_date
