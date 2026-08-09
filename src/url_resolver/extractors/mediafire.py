from bs4 import BeautifulSoup

class MediafireResolver:
    def extract_direct_url(self, html_content: str) -> str | None:
        soup = BeautifulSoup(html_content, "html.parser")
        btn = soup.find("a", id="downloadButton")
        if btn and btn.get("href"):
            return btn["href"]
        btn_aria = soup.find("a", attrs={"aria-label": "Download file"})
        if btn_aria and btn_aria.get("href"):
            return btn_aria["href"]
        return None
