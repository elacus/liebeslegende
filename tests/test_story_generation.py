import unittest
from unittest.mock import Mock

from google.genai import errors
from story_generation import (
    GeminiModelFallbackError,
    TEXT_MODELS,
    build_page_prompt,
    derive_poem_title,
    generate_content_with_fallback,
    is_distinct_poem,
    is_valid_poem,
    page_story_context,
    parse_poem_stanzas,
    repeated_poem_line_count,
)
from translations import detect_language


class ModelFallbackTests(unittest.TestCase):
    def test_text_models_use_current_fallback_order(self) -> None:
        self.assertEqual(
            TEXT_MODELS,
            (
                "gemini-3.8-flash",
                "gemini-3.7-flash",
                "gemini-3.6-flash",
            ),
        )

    def test_503_automatically_tries_next_model(self) -> None:
        client = Mock()
        response = object()
        client.models.generate_content.side_effect = [
            errors.APIError(
                503,
                {"error": {"code": 503, "message": "High demand"}},
            ),
            response,
        ]

        result = generate_content_with_fallback(
            client,
            ("text-model-one", "text-model-two"),
            ["prompt"],
            ["TEXT"],
        )

        self.assertIs(result, response)
        self.assertEqual(
            [
                call.kwargs["model"]
                for call in client.models.generate_content.call_args_list
            ],
            ["text-model-one", "text-model-two"],
        )

    def test_exhausted_fallback_reports_each_model(self) -> None:
        client = Mock()
        client.models.generate_content.side_effect = [
            errors.APIError(
                503,
                {"error": {"code": 503, "message": "High demand"}},
            ),
            errors.APIError(
                503,
                {"error": {"code": 503, "message": "Still unavailable"}},
            ),
        ]

        with self.assertRaises(GeminiModelFallbackError) as context:
            generate_content_with_fallback(
                client,
                ("text-model-one", "text-model-two"),
                ["prompt"],
                ["TEXT"],
            )

        self.assertIn("text-model-one returned 503", str(context.exception))
        self.assertIn("text-model-two returned 503", str(context.exception))
        self.assertEqual(context.exception.code, 503)


class PoemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.poem = (
            "Moonlight crowns the silver lake\n"
            "Softly wakes the dawn awake\n"
            "Roses guard the garden wall\n"
            "Fireflies answer every call\n\n"
            "The woodland opens wide\n"
            "Two hearts walk side by side\n"
            "A lantern warms the air\n"
            "They leave behind their care\n\n"
            "The castle greets the night\n"
            "Its windows shine so bright\n"
            "Their story finds its home\n"
            "No longer do they roam"
        )

    def test_parses_and_validates_three_quatrains(self) -> None:
        self.assertEqual(len(parse_poem_stanzas(self.poem)), 3)
        self.assertTrue(is_valid_poem(self.poem))

    def test_rejects_incomplete_stanzas(self) -> None:
        self.assertFalse(is_valid_poem("One line\n\nTwo lines\nStill two"))

    def test_derives_title_from_opening_line(self) -> None:
        self.assertEqual(derive_poem_title("Moonlight crowns the lake!\nNext line"), "Moonlight crowns the lake")

    def test_rejects_poems_repeating_four_lines(self) -> None:
        previous = self.poem
        current = (
            "Moonlight crowns the silver lake\n"
            "Softly wakes the dawn awake\n"
            "Roses guard the garden wall\n"
            "Fireflies answer every call\n\n"
            "Different woods surround the hill\n"
            "The river sleeps and all is still\n\n"
            "A new road crosses through the snow\n"
            "The travelers choose where they will"
        )
        self.assertEqual(repeated_poem_line_count(current, [previous]), 4)
        self.assertFalse(is_distinct_poem(current, [previous]))

    def test_page_prompt_carries_story_continuity(self) -> None:
        prompt = build_page_prompt(2, "English", "Watercolor", [self.poem])
        self.assertIn("Create page 2 of 5", prompt)
        self.assertIn("Previous story pages for continuity", prompt)
        self.assertIn(self.poem, prompt)

    def test_story_context_varies_by_page(self) -> None:
        self.assertIn("meeting for the first time", page_story_context(1))
        self.assertIn("happily-ever-after", page_story_context(5))


class TranslationTests(unittest.TestCase):
    def test_detect_language_normalizes_locale(self) -> None:
        self.assertEqual(detect_language("fr_CA"), "fr")
        self.assertEqual(detect_language("EN-us"), "en")
        self.assertEqual(detect_language("xx-YY"), "de")
        self.assertEqual(detect_language(None), "de")


if __name__ == "__main__":
    unittest.main()
