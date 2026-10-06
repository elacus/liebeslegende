from difflib import SequenceMatcher
import re
from io import BytesIO
from pathlib import Path

import streamlit as st
from fpdf import FPDF
from PIL import Image
from google import genai
from google.genai import errors
from google.genai import types

GEMINI_MODELS = (
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
)
GEMINI_FALLBACK_ERROR_CODES = {404, 408, 429, 500, 502, 503, 504}
CAMEO_PAGE_COUNT = 5

LANGUAGES = {
    "de": "Deutsch",
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
}

TEXT = {
    "de": {
        "title": "📖 Märchenhafter Liebesbuch-Generator",
        "intro": "Lade zwei Fotos hoch, um fünf märchenhafte Gedichtseiten mit passenden Illustrationen erstellen zu lassen.",
        "settings": "⚙️ Einstellungen",
        "language": "Sprache",
        "api_active": "API-Schlüssel aus Streamlit-Secrets aktiv",
        "style": "Märchen-Stil",
        "styles": ["Aquarell & Zauberwald", "Klassisches Königs-Märchen", "Sternenreise & Sternenlicht", "Rustikale Waldromantik"],
        "illustration_caption": "Generierte Märchen-Illustration",
        "download_poem": "Gedicht herunterladen",
        "pdf_error": "Das PDF konnte nicht erstellt werden: {error}",
        "person_1": "Foto Person 1 hochladen",
        "person_2": "Foto Person 2 hochladen",
        "caption_1": "Person 1",
        "caption_2": "Person 2",
        "generate": "✨ Liebes-Märchen generieren",
        "upload_warning": "Bitte lade beide Fotos hoch, damit die Charaktere analysiert werden können.",
        "spinner": "Fünf Gedichtseiten und passende Illustrationen werden erstellt …",
        "story_title": "📜 Dein persönliches Märchenbuch",
        "quota_error": "Das Kontingent für die Gemini-Bildgenerierung dieses Projekts ist ausgeschöpft (die API meldet ein Free-Tier-Limit von 0). Prüfe die Projektlimits und Abrechnung.\n\nHinweis: Laut API kannst du es in {retry_delay} erneut versuchen.",
        "retry_later": "einer Weile",
        "missing_key": "Kein API-Schlüssel in `.streamlit/secrets.toml` gefunden!",
        "error": "Beim Erstellen der Geschichte ist ein Fehler aufgetreten: {error}",
        "output_language": "Deutsch",
    },
    "en": {
        "title": "📖 Fairytale Love Book Generator",
        "intro": "Upload two photos to create five fairytale poem pages with matching illustrations.",
        "settings": "⚙️ Settings",
        "language": "Language",
        "api_active": "API key loaded from Streamlit secrets",
        "style": "Fairytale style",
        "styles": ["Watercolor & enchanted forest", "Classic royal fairytale", "Star journey & starlight", "Rustic forest romance"],
        "illustration_caption": "Generated fairytale illustration",
        "download_poem": "Download poem",
        "pdf_error": "The PDF could not be created: {error}",
        "person_1": "Upload photo of person 1",
        "person_2": "Upload photo of person 2",
        "caption_1": "Person 1",
        "caption_2": "Person 2",
        "generate": "✨ Generate love fairytale",
        "upload_warning": "Please upload both photos so the characters can be analyzed.",
        "spinner": "Creating five poem pages and matching illustrations …",
        "story_title": "📜 Your personal fairytale book",
        "quota_error": "The Gemini image-generation quota for this project has been exhausted (the API reports a free-tier limit of 0). Check the project limits and billing.\n\nNote: The API says you can try again in {retry_delay}.",
        "retry_later": "a while",
        "missing_key": "No API key found in `.streamlit/secrets.toml`!",
        "error": "An error occurred while creating the story: {error}",
        "output_language": "English",
    },
    "fr": {
        "title": "📖 Générateur de livre de conte romantique",
        "intro": "Importez deux photos pour créer cinq pages de poèmes féeriques avec des illustrations assorties.",
        "settings": "⚙️ Paramètres",
        "language": "Langue",
        "api_active": "Clé API chargée depuis les secrets Streamlit",
        "style": "Style du conte",
        "styles": ["Aquarelle et forêt enchantée", "Conte royal classique", "Voyage parmi les étoiles", "Romance rustique en forêt"],
        "illustration_caption": "Illustration de conte générée",
        "download_poem": "Télécharger le poème",
        "pdf_error": "Impossible de créer le PDF : {error}",
        "person_1": "Importer la photo de la personne 1",
        "person_2": "Importer la photo de la personne 2",
        "caption_1": "Personne 1",
        "caption_2": "Personne 2",
        "generate": "✨ Créer le conte romantique",
        "upload_warning": "Veuillez importer les deux photos pour permettre l’analyse des personnages.",
        "spinner": "Création de cinq pages de poèmes et d’illustrations assorties …",
        "story_title": "📜 Votre livre de conte personnalisé",
        "quota_error": "Le quota de génération d’images Gemini de ce projet est épuisé (l’API indique une limite gratuite de 0). Vérifiez les limites du projet et la facturation.\n\nRemarque : l’API indique que vous pouvez réessayer dans {retry_delay}.",
        "retry_later": "quelque temps",
        "missing_key": "Aucune clé API trouvée dans `.streamlit/secrets.toml` !",
        "error": "Une erreur s’est produite lors de la création du conte : {error}",
        "output_language": "français",
    },
    "es": {
        "title": "📖 Generador de cuentos románticos",
        "intro": "Sube dos fotos para crear cinco páginas de poemas de cuento con ilustraciones a juego.",
        "settings": "⚙️ Ajustes",
        "language": "Idioma",
        "api_active": "Clave de API cargada desde los secretos de Streamlit",
        "style": "Estilo del cuento",
        "styles": ["Acuarela y bosque encantado", "Cuento clásico de reyes", "Viaje entre estrellas", "Romance rústico en el bosque"],
        "illustration_caption": "Ilustración de cuento generada",
        "download_poem": "Descargar poema",
        "pdf_error": "No se pudo crear el PDF: {error}",
        "person_1": "Subir foto de la persona 1",
        "person_2": "Subir foto de la persona 2",
        "caption_1": "Persona 1",
        "caption_2": "Persona 2",
        "generate": "✨ Crear cuento romántico",
        "upload_warning": "Sube ambas fotos para poder analizar a los personajes.",
        "spinner": "Creando cinco páginas de poemas e ilustraciones a juego …",
        "story_title": "📜 Tu cuento personalizado",
        "quota_error": "Se ha agotado la cuota de generación de imágenes de Gemini para este proyecto (la API indica un límite gratuito de 0). Comprueba los límites del proyecto y la facturación.\n\nAviso: la API indica que puedes volver a intentarlo en {retry_delay}.",
        "retry_later": "un tiempo",
        "missing_key": "No se encontró la clave de API en `.streamlit/secrets.toml`.",
        "error": "Se produjo un error al crear el cuento: {error}",
        "output_language": "español",
    },
    "it": {
        "title": "📖 Generatore di fiabe romantiche",
        "intro": "Carica due foto per creare cinque pagine di poesie fiabesche con illustrazioni abbinate.",
        "settings": "⚙️ Impostazioni",
        "language": "Lingua",
        "api_active": "Chiave API caricata dai secrets di Streamlit",
        "style": "Stile della fiaba",
        "styles": ["Acquerello e foresta incantata", "Fiaba classica di corte", "Viaggio tra le stelle", "Romantico bosco rustico"],
        "illustration_caption": "Illustrazione fiabesca generata",
        "download_poem": "Scarica la poesia",
        "pdf_error": "Impossibile creare il PDF: {error}",
        "person_1": "Carica la foto della persona 1",
        "person_2": "Carica la foto della persona 2",
        "caption_1": "Persona 1",
        "caption_2": "Persona 2",
        "generate": "✨ Genera la fiaba romantica",
        "upload_warning": "Carica entrambe le foto per consentire l’analisi dei personaggi.",
        "spinner": "Creazione di cinque pagine di poesie e illustrazioni abbinate …",
        "story_title": "📜 La tua fiaba personalizzata",
        "quota_error": "La quota di generazione immagini Gemini per questo progetto è esaurita (l’API indica un limite gratuito pari a 0). Controlla i limiti del progetto e la fatturazione.\n\nNota: l’API indica che puoi riprovare tra {retry_delay}.",
        "retry_later": "un po’ di tempo",
        "missing_key": "Chiave API non trovata in `.streamlit/secrets.toml`.",
        "error": "Si è verificato un errore durante la creazione della fiaba: {error}",
        "output_language": "italiano",
    },
}

PDF_FONT_PAIRS = (
    (
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ),
    (
        Path("/Library/Fonts/Arial.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
    ),
)


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


class IncompleteGeneratedPageError(RuntimeError):
    pass


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


def create_poem_pdf(
    pages: list[tuple[str, bytes | None]], cover_title: str
) -> bytes:
    """Create an A4 booklet with a cover and five illustrated poem pages."""
    font_pair = next(
        (
            (regular, bold)
            for regular, bold in PDF_FONT_PAIRS
            if regular.is_file() and bold.is_file()
        ),
        None,
    )
    if font_pair is None:
        raise FileNotFoundError("No Unicode TrueType font is available for PDF generation.")

    if len(pages) != CAMEO_PAGE_COUNT:
        raise ValueError(f"The book must contain exactly {CAMEO_PAGE_COUNT} pages.")
    if any(not is_valid_poem(poem) for poem, _ in pages):
        raise ValueError("Each poem must contain exactly three stanzas of four lines.")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_font("Book", fname=str(font_pair[0]))
    pdf.add_font("Book", style="B", fname=str(font_pair[1]))

    pdf.add_page()
    pdf.set_fill_color(248, 244, 235)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    pdf.set_draw_color(166, 126, 76)
    pdf.set_line_width(1.2)
    pdf.rect(12, 12, pdf.w - 24, pdf.h - 24)
    pdf.set_line_width(0.35)
    pdf.rect(17, 17, pdf.w - 34, pdf.h - 34)
    pdf.set_fill_color(112, 74, 87)
    for x, y, diameter in (
        (36, 50, 3),
        (pdf.w - 39, 50, 3),
        (36, pdf.h - 53, 3),
        (pdf.w - 39, pdf.h - 53, 3),
    ):
        pdf.ellipse(x, y, diameter, diameter, style="F")
    pdf.set_fill_color(166, 126, 76)
    pdf.ellipse(pdf.w / 2 - 2.5, 72, 5, 5, style="F")
    pdf.set_text_color(49, 57, 73)
    pdf.set_font("Book", style="B", size=30)
    pdf.set_xy(28, 111)
    pdf.multi_cell(pdf.w - 56, 17, cover_title, align="C")
    pdf.set_draw_color(166, 126, 76)
    pdf.set_line_width(0.8)
    pdf.line(63, 166, pdf.w - 63, 166)
    pdf.set_fill_color(112, 74, 87)
    pdf.ellipse(pdf.w / 2 - 1.5, 179, 3, 3, style="F")

    margin = 18
    for page_number, (poem, image_data) in enumerate(pages, start=1):
        pdf.add_page()
        pdf.set_fill_color(252, 250, 246)
        pdf.rect(0, 0, pdf.w, pdf.h, style="F")
        pdf.set_draw_color(211, 197, 177)
        pdf.set_line_width(0.4)
        pdf.line(margin, 13, pdf.w - margin, 13)
        pdf.set_font("Book", style="B", size=9)
        pdf.set_text_color(112, 74, 87)
        pdf.set_xy(margin, 17)
        pdf.cell(pdf.w - 2 * margin, 7, f"{page_number:02d}", align="R")

        image_y = 30
        if image_data is not None:
            with Image.open(BytesIO(image_data)) as illustration:
                image_width, image_height = illustration.size
            max_image_width = pdf.w - 2 * margin
            max_image_height = 142
            scale = min(
                max_image_width / image_width,
                max_image_height / image_height,
            )
            rendered_width = image_width * scale
            rendered_height = image_height * scale
            image_x = (pdf.w - rendered_width) / 2
            pdf.image(
                BytesIO(image_data),
                x=image_x,
                y=image_y,
                w=rendered_width,
                h=rendered_height,
            )
            poem_y = image_y + rendered_height + 10
        else:
            poem_y = 77

        pdf.set_text_color(49, 57, 73)
        pdf.set_font("Book", size=12)
        pdf.set_xy(margin, poem_y)
        for stanza_index, stanza in enumerate(parse_poem_stanzas(poem)):
            for line in stanza:
                pdf.cell(pdf.w - 2 * margin, 7.2, line, align="C", new_x="LMARGIN", new_y="NEXT")
            if stanza_index < 2:
                pdf.ln(3)

    return bytes(pdf.output())


def detect_language(locale: str | None) -> str:
    """Map the browser's locale to a supported language."""
    if locale:
        language_code = locale.replace("_", "-").split("-", maxsplit=1)[0].lower()
        if language_code in LANGUAGES:
            return language_code
    return "de"


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


# ---------------------------------------------------------
# Seitentitel und Konfiguration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Fairytale Love Book Generator",
    page_icon="📖",
    layout="wide"
)

if "language_code" not in st.session_state:
    st.session_state.language_code = detect_language(st.context.locale)

language_code = st.session_state.language_code
text = TEXT[language_code]

with st.sidebar:
    st.header(text["settings"])
    language_code = st.selectbox(
        text["language"],
        options=list(LANGUAGES),
        format_func=LANGUAGES.__getitem__,
        key="language_code",
    )

text = TEXT[language_code]
if "GEMINI_API_KEY" not in st.secrets:
    st.error(text["missing_key"])
    st.stop()
api_key = st.secrets["GEMINI_API_KEY"]

st.title(text["title"])
st.write(text["intro"])

# ---------------------------------------------------------
# Seitenleiste Einstellungen
# ---------------------------------------------------------
with st.sidebar:
    st.success(text["api_active"])
    st.markdown("---")
    stil = st.selectbox(
        f"{text['style']}:",
        text["styles"],
    )

# ---------------------------------------------------------
# Upload-Bereich für die Fotos
# ---------------------------------------------------------
col_up1, col_up2 = st.columns(2)

with col_up1:
    foto_person_1 = st.file_uploader(text["person_1"], type=["jpg", "jpeg", "png"])
    if foto_person_1:
        img1 = Image.open(foto_person_1)
        st.image(img1, caption=text["caption_1"], width="stretch")

with col_up2:
    foto_person_2 = st.file_uploader(text["person_2"], type=["jpg", "jpeg", "png"])
    if foto_person_2:
        img2 = Image.open(foto_person_2)
        st.image(img2, caption=text["caption_2"], width="stretch")

# ---------------------------------------------------------
# Generierung auslösen
# ---------------------------------------------------------
if st.button(text["generate"], type="primary", width="stretch"):
    if not foto_person_1 or not foto_person_2:
        st.warning(text["upload_warning"])
    else:
        for key in ("generated_pages", "generated_language_code"):
            st.session_state.pop(key, None)

        with st.spinner(text["spinner"]):
            try:
                client = genai.Client(api_key=api_key)
                gemini_init_error = None
            except Exception as e:
                client = None
                gemini_init_error = e
            generated_pages: list[tuple[str, bytes | None]] = []
            previous_poems: list[str] = []
            generation_error = None
            quota_warning_shown = False

            for page_number in range(1, CAMEO_PAGE_COUNT + 1):
                try:
                    if client is None:
                        raise RuntimeError(
                            "Gemini client could not be initialized."
                        ) from gemini_init_error
                    poem, image_data = generate_gemini_page(
                        client,
                        img1,
                        img2,
                        stil,
                        text["output_language"],
                        page_number,
                        previous_poems,
                    )
                except errors.APIError as e:
                    if e.code == 429 and not quota_warning_shown:
                        quota_warning_shown = True
                        retry_delay = format_retry_delay(e) or text["retry_later"]
                        st.error(
                            text["quota_error"].format(retry_delay=retry_delay)
                        )
                    generation_error = e
                    break
                except Exception as e:
                    generation_error = e
                    break

                if not is_distinct_poem(poem, previous_poems):
                    generation_error = IncompleteGeneratedPageError(
                        f"Generated poem for page {page_number} repeats earlier content."
                    )
                    break

                generated_pages.append((poem, image_data))
                previous_poems.append(poem)

            if generation_error is not None:
                st.error(text["error"].format(error=generation_error))
            elif len(generated_pages) == CAMEO_PAGE_COUNT:
                st.session_state.generated_pages = generated_pages
                st.session_state.generated_language_code = language_code

if (
    "generated_pages" in st.session_state
    and "generated_language_code" in st.session_state
):
    generated_language = st.session_state.generated_language_code
    generated_text = TEXT[generated_language]
    pages = st.session_state.generated_pages
    book_title = derive_poem_title(pages[0][0])

    st.markdown("---")
    st.subheader(generated_text["story_title"])
    st.markdown(f"### {book_title}")
    for page_number, (poem, image_data) in enumerate(pages, start=1):
        st.markdown(f"### {page_number}")
        if image_data is not None:
            st.image(
                Image.open(BytesIO(image_data)),
                caption=generated_text["illustration_caption"],
                width="stretch",
                alt=generated_text["illustration_caption"],
            )
        st.markdown(poem)

    try:
        pdf_data = create_poem_pdf(pages, book_title)
    except Exception as e:
        st.error(generated_text["pdf_error"].format(error=e))
    else:
        st.download_button(
            label=text["download_poem"],
            data=pdf_data,
            file_name=f"liebesgedicht-{generated_language}.pdf",
            mime="application/pdf",
            type="primary",
        )