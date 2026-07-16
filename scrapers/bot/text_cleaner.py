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

        # 1. Strip trailing or excessive hashtag blocks (e.g., #opportunity #hiring #tech)
        # Matches # followed by alphanumeric characters, trailing at the end or clustered
        text = re.sub(r'(#\w+\s*)+$', '', text)
        # Clean inline hashtags but keep the word (e.g., "This #hiring event" -> "This hiring event")
        text = re.sub(r'#(\w+)', r'\1', text)

        # 2. Clean up repetitive, trailing emoji blocks to keep text readable
        # This reduces long strings of identical icons down to a single instance
        text = re.sub(r'([\u2600-\u1F9FF])\1+', r'\1', text)

        # 3. Collapse multiple spaces or newlines down to clean spacing
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    @staticmethod
    def resolve_short_link(short_url: str) -> str:
        """Resolves tracking shortcodes (like lnkd.in redirects) back to original destinations."""
        if not short_url or ("lnkd.in" not in short_url and "bit.ly" not in short_url):
            return short_url
            
        try:
            # Send a fast HEAD request to grab the redirect location header without downloading body bytes
            opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
            request = urllib.request.Request(short_url, method="HEAD")
            with opener.open(request) as response:
                return response.geturl()
        except Exception:
            # Fallback to short URL if resolution fails due to network walls or token timeouts
            return short_url