from io import BytesIO

import streamlit as st
from google import genai
from google.genai import errors
from PIL import Image

from pdf_book import create_poem_pdf
from story_generation import (
    CAMEO_PAGE_COUNT,
    IncompleteGeneratedPageError,
    derive_poem_title,
    format_retry_delay,
    generate_gemini_page,
    is_distinct_poem,
)
from translations import LANGUAGES, TEXT, detect_language

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