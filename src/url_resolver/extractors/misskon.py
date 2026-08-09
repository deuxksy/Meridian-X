from bs4 import BeautifulSoup
from url_resolver.extractors.base import BaseExtractor

class MisskonParser(BaseExtractor):
    def extract_download_links(self, html_content: str) -> list[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(domain in href for domain in ["ouo.io", "ouo.press", "mediafire.com", "mega.nz"]):
                links.append(href)
        return list(dict.fromkeys(links))
