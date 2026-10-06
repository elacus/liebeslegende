from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from PIL import Image

from story_generation import CAMEO_PAGE_COUNT, is_valid_poem, parse_poem_stanzas

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


def create_poem_pdf(
    pages: list[tuple[str, bytes | None]],
    cover_title: str,
    image_placeholder_text: str = "Illustration unavailable",
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
            placeholder_width = pdf.w - 2 * margin
            placeholder_height = 105
            pdf.set_fill_color(242, 237, 229)
            pdf.set_draw_color(211, 197, 177)
            pdf.rect(
                margin,
                image_y,
                placeholder_width,
                placeholder_height,
                style="DF",
            )
            pdf.set_text_color(112, 74, 87)
            pdf.set_font("Book", style="B", size=13)
            pdf.set_xy(margin, image_y + placeholder_height / 2 - 6)
            pdf.cell(
                placeholder_width,
                12,
                image_placeholder_text,
                align="C",
            )
            poem_y = image_y + placeholder_height + 10

        pdf.set_text_color(49, 57, 73)
        pdf.set_font("Book", size=12)
        pdf.set_xy(margin, poem_y)
        for stanza_index, stanza in enumerate(parse_poem_stanzas(poem)):
            for line in stanza:
                pdf.cell(
                    pdf.w - 2 * margin,
                    7.2,
                    line,
                    align="C",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            if stanza_index < 2:
                pdf.ln(3)

    return bytes(pdf.output())
