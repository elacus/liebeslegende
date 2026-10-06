from difflib import SequenceMatcher
from io import BytesIO
import re

from google import genai
from google.genai import errors, types
from PIL import Image

CAMEO_PAGE_COUNT = 5
GEMINI_MODELS = (
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
)
GEMINI_FALLBACK_ERROR_CODES = {404, 408, 429, 500, 502, 503, 504}


class IncompleteGeneratedPageError(RuntimeError):
    pass


def parse_poem_stanzas(poem: str) -> list[list[str]]:
    """Split a poem into its non-empty stanzas."""
    stanzas = []
    current_stanza = []
    for line in poem.splitlines():
        if line.strip():
            current_stanza.append(line)
        elif current_stanza:
            stanzas.append(current_stanza)
            current_stanza = []
    if current_stanza:
        stanzas.append(current_stanza)
    return stanzas


def is_valid_poem(poem: str) -> bool:
    """Check the required three quatrains before saving a generated page."""
    stanzas = parse_poem_stanzas(poem)
    return len(stanzas) == 3 and all(len(stanza) == 4 for stanza in stanzas)


def is_distinct_poem(poem: str, previous_poems: list[str]) -> bool:
    """Reject empty poems and drafts that reuse most verses from an earlier page."""
    return bool(re.sub(r"\W+", "", poem)) and repeated_poem_line_count(
        poem,
        previous_poems,
    ) < 4


def repeated_poem_line_count(poem: str, previous_poems: list[str]) -> int:
    """Count verses closely matching an earlier poem, matched one-to-one."""
    current_lines = [
        re.sub(r"\W+", " ", line.casefold()).strip()
        for stanza in parse_poem_stanzas(poem)
        for line in stanza
    ]
    highest_match_count = 0
    for previous in previous_poems:
        previous_lines = [
            re.sub(r"\W+", " ", line.casefold()).strip()
            for stanza in parse_poem_stanzas(previous)
            for line in stanza
        ]
        matches = sorted(
            (
                SequenceMatcher(
                    None,
                    current_line,
                    previous_line,
                    autojunk=False,
                ).ratio(),
                current_index,
                previous_index,
            )
            for current_index, current_line in enumerate(current_lines)
            for previous_index, previous_line in enumerate(previous_lines)
            if current_line and previous_line
        )
        used_current_lines = set()
        used_previous_lines = set()
        matched_count = 0
        for similarity, current_index, previous_index in reversed(matches):
            if similarity < 0.9:
                break
            if (
                current_index not in used_current_lines
                and previous_index not in used_previous_lines
            ):
                used_current_lines.add(current_index)
                used_previous_lines.add(previous_index)
                matched_count += 1
        highest_match_count = max(highest_match_count, matched_count)
    return highest_match_count


def derive_poem_title(poem: str) -> str:
    """Use the opening line as an incipit title for the book cover."""
    stanzas = parse_poem_stanzas(poem)
    if not stanzas or not stanzas[0]:
        raise ValueError("The first poem has no opening line for the cover title.")
    return stanzas[0][0].strip().rstrip(" .!?…")


def page_story_context(page_number: int) -> str:
    return (
        "Show the couple meeting for the first time in an enchanted forest."
        if page_number == 1
        else "They discover a hidden moonlit path and a magical map that points toward a distant castle."
        if page_number == 2
        else "A sudden storm extinguishes the map's guiding light; show the couple facing this challenge together."
        if page_number == 3
        else "Show the couple restoring the guiding light through trust, courage, and a kind act."
        if page_number == 4
        else "Conclude with a distinct celebration at the castle and the couple's joyful happily-ever-after."
    )


def build_page_prompt(
    page_number: int,
    output_language: str,
    style: str,
    previous_poems: list[str],
) -> str:
    previous_context = "\n\n".join(previous_poems)
    if previous_context:
        previous_context = f"Previous story pages for continuity:\n{previous_context}\n"
    return f"""
    Create page {page_number} of {CAMEO_PAGE_COUNT} in a romantic fairytale photo book.
    Analyze both uploaded photos and portray both people as recognizable, consistent main characters.
    Fairytale style: "{style}".
    Story direction for this page: {page_story_context(page_number)}
    {previous_context}

    Return a unique romantic poem in {output_language} with exactly 12 lines,
    grouped into exactly 3 stanzas of 4 lines each. Use the AABB rhyme scheme in
    every stanza: lines 1 and 2 rhyme (A), and lines 3 and 4 rhyme (B).
    Separate stanzas with one blank line.
    Choose simple, unmistakable rhyme pairs. Separate stanzas with one blank line.
    Make this page's poem substantially different from every previous poem. Do not reuse
    any previous line, image, event, or distinctive phrase. Follow this page's story direction
    with its own concrete scene and advance the overall story.
    Return only the poem, with no title, numbering, headings, explanations, or other text.

    Also generate exactly one finished watercolor children's-book illustration for this page.
    Base the illustration on the exact poem you just wrote: depict its setting, actions,
    and emotional tone. Show the same two main characters acting out that poem, rather
    than creating a separate scene for the page.
    The output must be an actual image without text, letters, captions, or watermark.
    """


def generate_gemini_page(
    client: genai.Client,
    img1: Image.Image,
    img2: Image.Image,
    style: str,
    output_language: str,
    page_number: int,
    previous_poems: list[str],
) -> tuple[str, bytes]:
    prompt = build_page_prompt(
        page_number,
        output_language,
        style,
        previous_poems,
    )
    for model_index, model in enumerate(GEMINI_MODELS):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[img1, img2, prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
            break
        except errors.APIError as e:
            if (
                e.code not in GEMINI_FALLBACK_ERROR_CODES
                or model_index == len(GEMINI_MODELS) - 1
            ):
                raise

    response_parts = response.parts or []
    poem = "".join(part.text or "" for part in response_parts).strip()
    if (
        not is_valid_poem(poem)
        or not is_distinct_poem(poem, previous_poems)
    ):
        raise IncompleteGeneratedPageError(
            f"Gemini did not return a distinct 12-line poem in three four-line "
            f"stanzas for page {page_number}."
        )

    for part in response_parts:
        if (
            part.inline_data
            and part.inline_data.data
            and (part.inline_data.mime_type or "").startswith("image/")
        ):
            with Image.open(BytesIO(part.inline_data.data)) as image:
                image_buffer = BytesIO()
                image.convert("RGB").save(image_buffer, format="PNG")
            return poem, image_buffer.getvalue()
    raise IncompleteGeneratedPageError(
        f"Gemini did not return an illustration for page {page_number}."
    )


def format_retry_delay(error: errors.APIError) -> str | None:
    """Format the retry delay returned in Gemini API quota error details."""
    details = error.details
    if not isinstance(details, dict):
        return None

    error_details = details.get("error", details).get("details", [])
    if not isinstance(error_details, list):
        return None

    for detail in error_details:
        if not isinstance(detail, dict) or not detail.get("@type", "").endswith("RetryInfo"):
            continue
        retry_delay = detail.get("retryDelay", "")
        match = re.fullmatch(r"(\d+(?:\.\d+)?)s", retry_delay)
        if not match:
            return None
        total_minutes = int(float(match.group(1)) // 60)
        hours, minutes = divmod(total_minutes, 60)
        if hours and minutes:
            return f"{hours} h {minutes} min"
        if hours:
            return f"{hours} h"
        if minutes:
            return f"{minutes} min"
        return "< 1 min"
    return None
