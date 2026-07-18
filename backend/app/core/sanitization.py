import re

import nh3

# Tag/attribute allowlist applied to every stored newsletter body. Note that
# `style` is intentionally NOT allowed on any element: attacker-controlled inline
# CSS enables data exfiltration / clickjacking in feed readers that honor it.
ALLOWED_TAGS = {
    "p",
    "strong",
    "em",
    "u",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "br",
    "div",
    "span",
    "figure",
    "figcaption",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
}


def sanitize_html(raw_html_content: str | None) -> str:
    """Decode, strip control chars, and sanitize HTML to the allowlist."""
    if not raw_html_content:
        return ""

    # Remove NULL bytes and other control characters that can cause lxml/nh3 to fail.
    # We keep tab (\x09), newline (\x0a), and carriage return (\x0d)
    clean_html_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw_html_content)

    return nh3.clean(clean_html_str, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
