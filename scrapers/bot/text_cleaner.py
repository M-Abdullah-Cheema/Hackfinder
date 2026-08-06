import re
import urllib.request


class SocialMediaSanitizer:
    """
    Cleans conversational and social media text structures by removing
    excessive hashtag noise, managing emojis, and resolving short links.
    """

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""

        # Drop common CTA / engagement spam lines
        lines = []
        for line in text.splitlines():
            low = line.strip().lower()
            if not low:
                continue
            if any(
                phrase in low
                for phrase in (
                    "link in bio",
                    "follow us",
                    "like and share",
                    "double tap",
                    "tag a friend",
                    "comment below",
                    "send this to",
                )
            ):
                continue
            lines.append(line)
        text = "\n".join(lines) if lines else text

        # Strip trailing hashtag blocks
        text = re.sub(r"(#\w+\s*)+$", "", text, flags=re.MULTILINE)
        # Keep hashtag words without the #
        text = re.sub(r"#(\w+)", r"\1", text)
        # Soften @handles to plain names
        text = re.sub(r"@([\w.]+)", r"\1", text)

        # Collapse repetitive emoji runs
        text = re.sub(r"([\U00002600-\U0001F9FF])\1+", r"\1", text)

        # Collapse whitespace but keep paragraph breaks
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    @staticmethod
    def resolve_short_link(short_url: str) -> str:
        """Resolves tracking shortcodes (like lnkd.in redirects) back to original destinations."""
        if not short_url or ("lnkd.in" not in short_url and "bit.ly" not in short_url):
            return short_url

        try:
            opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
            request = urllib.request.Request(short_url, method="HEAD")
            with opener.open(request) as response:
                return response.geturl()
        except Exception:
            return short_url
