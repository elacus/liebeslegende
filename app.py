import base64
from difflib import SequenceMatcher
import json
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import streamlit as st
from fpdf import FPDF
from PIL import Image, ImageOps
from google import genai
from google.genai import errors
from google.genai import types

GEMINI_MODELS = (
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
)
GEMINI_FALLBACK_ERROR_CODES = {404, 408, 429, 500, 502, 503, 504}
CAMEO_PAGE_COUNT = 5
MAX_CLOUDFLARE_POEM_ATTEMPTS = 3
OUTPUT_LANGUAGE_CODES = {
    "deutsch": "de",
    "english": "en",
    "français": "fr",
    "español": "es",
    "italiano": "it",
}
RHYME_EXAMPLES = {
    "de": ("Nacht/Wacht", "Licht/Gesicht", "Hand/Land", "Herz/Schmerz", "Traum/kaum", "Tor/davor"),
    "en": ("night/light", "stream/dream", "glow/know", "heart/start", "day/way", "near/year"),
    "fr": ("nuit/bruit", "amour/toujours", "lumière/rivière", "cœur/bonheur", "saison/maison", "espoir/soir"),
    "es": ("amor/calor", "canción/corazón", "vida/herida", "cielo/suelo", "estrella/bella", "camino/destino"),
    "it": ("amore/cuore", "sole/parole", "sereno/terreno", "canzone/emozione", "destino/vicino", "sera/vera"),
}
CLOUDFLARE_VISION_MODEL = "@cf/llava-hf/llava-1.5-7b-hf"
CLOUDFLARE_IMAGE_MODEL = "@cf/bytedance/stable-diffusion-xl-lightning"
CLOUDFLARE_VISION_DOC_URL = (
    "https://developers.cloudflare.com/workers-ai/models/llava-1.5-7b-hf/"
)
CLOUDFLARE_REST_API_DOC_URL = (
    "https://developers.cloudflare.com/workers-ai/get-started/rest-api/"
)

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
        "continue_without_image": "Weiter ohne Bildgenerierung",
        "poem_only_spinner": "Gedicht wird ohne Bildgenerierung erstellt …",
        "poem_only_error": "Das Gedicht konnte ohne Bildgenerierung nicht erstellt werden: {error}",
        "cloudflare_fallback": "Gemini ist nicht verfügbar. Cloudflare wird als Fallback versucht.",
        "cloudflare_image_error": "Cloudflare konnte das Gedicht erstellen, aber kein Bild generieren: {error} Du kannst ohne Bild fortfahren.",
        "some_illustrations_missing": "Mindestens eine Illustration konnte nicht erstellt werden. Du kannst mit dem Button unten ohne Bilder fortfahren.",
        "cloudflare_error": "Auch der Cloudflare-Fallback ist fehlgeschlagen: {error}",
        "cloudflare_auth_error": "Cloudflare hat die Anmeldung abgelehnt. Prüfe die Account-ID und erstelle im Cloudflare-Dashboard unter „Workers AI“ einen Workers-AI-API-Token. Ein manuell erstellter Token benötigt die Berechtigungen „Workers AI – Read“ und „Workers AI – Edit“. Ersetze damit CLOUDFLARE_ACCOUNT_ID und CLOUDFLARE_API_TOKEN in der secrets.toml dieser App.",
        "cloudflare_auth_docs": "Cloudflare-Anleitung: API-Token für Workers AI erstellen",
        "cloudflare_license_notice": "Cloudflare verlangt für dieses Vision-Modell die Zustimmung zu einer Lizenz und Nutzungsrichtlinie. Diese Bedingungen enthalten eine Erklärung, dass die nutzende Person nicht in der EU wohnhaft ist beziehungsweise das Unternehmen seinen Hauptsitz nicht in der EU hat. Wenn das auf dich nicht zutrifft, bestätige die Zustimmung nicht. Der Fallback wurde auf ein anderes Cloudflare-Vision-Modell umgestellt.",
        "cloudflare_vision_docs": "Informationen zum alternativen Cloudflare-Visionmodell",
        "without_illustration": "Das PDF wird ohne generierte Illustration erstellt.",
        "pdf_error": "Das PDF konnte nicht erstellt werden: {error}",
        "person_1": "Foto Person 1 hochladen",
        "person_2": "Foto Person 2 hochladen",
        "caption_1": "Person 1",
        "caption_2": "Person 2",
        "generate": "✨ Liebes-Märchen generieren",
        "upload_warning": "Bitte lade beide Fotos hoch, damit die Charaktere analysiert werden können.",
        "spinner": "Fünf Gedichtseiten und passende Illustrationen werden erstellt …",
        "story_title": "📜 Dein persönliches Märchenbuch",
        "fallback": "Das Modell {model} war vorübergehend nicht verfügbar. Gedicht und Illustration wurden mit einem Ausweichmodell erstellt.",
        "incomplete_output": "Das Modell hat für eine Seite nicht das angeforderte Gedicht mit 3 AABB-Strophen à 4 Zeilen und eine Illustration geliefert. Bitte versuche es erneut.",
        "incomplete_poem_only": "Das Modell hat nicht fünf Gedichte mit jeweils 3 AABB-Strophen à 4 Zeilen geliefert. Bitte versuche es erneut.",
        "quota_error": "Das Kontingent für die Gemini-Bildgenerierung dieses Projekts ist ausgeschöpft (die API meldet ein Free-Tier-Limit von 0). Prüfe die Projektlimits und Abrechnung. Ein Fallback-Modell kann bei ebenfalls ausgeschöpftem Kontingent auch fehlschlagen.\n\nHinweis: Laut API kannst du es in {retry_delay} erneut versuchen.",
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
        "continue_without_image": "Continue without image generation",
        "poem_only_spinner": "Generating the poem without image generation …",
        "poem_only_error": "The poem could not be generated without an image: {error}",
        "cloudflare_fallback": "Gemini is unavailable. Trying Cloudflare as a fallback.",
        "cloudflare_image_error": "Cloudflare generated the poem but could not generate an image: {error} You can continue without an image.",
        "some_illustrations_missing": "At least one illustration could not be generated. Use the button below to continue without images.",
        "cloudflare_error": "The Cloudflare fallback also failed: {error}",
        "cloudflare_auth_error": "Cloudflare rejected authentication. Check the account ID and create a Workers AI API token in the Cloudflare dashboard under Workers AI. A manually created token needs both Workers AI - Read and Workers AI - Edit permissions. Replace CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in this app's secrets.toml.",
        "cloudflare_auth_docs": "Cloudflare guide: create a Workers AI API token",
        "cloudflare_license_notice": "Cloudflare requires agreement to a license and acceptable-use policy for this vision model. These terms include a representation that the user is not domiciled in the EU and the company does not have its principal place of business in the EU. If that does not apply to you, do not submit the agreement. The fallback has been switched to a different Cloudflare vision model.",
        "cloudflare_vision_docs": "Information about the alternative Cloudflare vision model",
        "without_illustration": "The PDF will be created without a generated illustration.",
        "pdf_error": "The PDF could not be created: {error}",
        "person_1": "Upload photo of person 1",
        "person_2": "Upload photo of person 2",
        "caption_1": "Person 1",
        "caption_2": "Person 2",
        "generate": "✨ Generate love fairytale",
        "upload_warning": "Please upload both photos so the characters can be analyzed.",
        "spinner": "Creating five poem pages and matching illustrations …",
        "story_title": "📜 Your personal fairytale book",
        "fallback": "The model {model} was temporarily unavailable. The poem and illustration were generated with a fallback model.",
        "incomplete_output": "The model did not return the requested poem with 3 AABB stanzas of 4 lines and an illustration for a page. Please try again.",
        "incomplete_poem_only": "The model did not return five poems with 3 AABB stanzas of 4 lines each. Please try again.",
        "quota_error": "The Gemini image-generation quota for this project has been exhausted (the API reports a free-tier limit of 0). Check the project limits and billing. A fallback model can also fail if its quota is exhausted.\n\nNote: The API says you can try again in {retry_delay}.",
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
        "continue_without_image": "Continuer sans générer d’image",
        "poem_only_spinner": "Création du poème sans génération d’image …",
        "poem_only_error": "Impossible de créer le poème sans image : {error}",
        "cloudflare_fallback": "Gemini est indisponible. Tentative de recours à Cloudflare.",
        "cloudflare_image_error": "Cloudflare a créé le poème, mais n’a pas pu générer d’image : {error} Vous pouvez continuer sans image.",
        "some_illustrations_missing": "Au moins une illustration n’a pas pu être créée. Utilisez le bouton ci-dessous pour continuer sans images.",
        "cloudflare_error": "Le recours à Cloudflare a également échoué : {error}",
        "cloudflare_auth_error": "Cloudflare a refusé l’authentification. Vérifiez l’identifiant du compte et créez un jeton API Workers AI dans le tableau de bord Cloudflare, sous Workers AI. Un jeton créé manuellement doit avoir les autorisations « Workers AI - Read » et « Workers AI - Edit ». Remplacez CLOUDFLARE_ACCOUNT_ID et CLOUDFLARE_API_TOKEN dans le fichier secrets.toml de cette application.",
        "cloudflare_auth_docs": "Guide Cloudflare : créer un jeton API Workers AI",
        "cloudflare_license_notice": "Cloudflare exige l’acceptation d’une licence et d’une politique d’utilisation pour ce modèle visuel. Ces conditions comprennent une déclaration indiquant que l’utilisateur ne réside pas dans l’UE et que l’entreprise n’y a pas son siège principal. Si cela ne s’applique pas à vous, n’acceptez pas ces conditions. Le modèle visuel de secours Cloudflare a été remplacé par un autre.",
        "cloudflare_vision_docs": "Informations sur l’autre modèle visuel Cloudflare",
        "without_illustration": "Le PDF sera créé sans illustration générée.",
        "pdf_error": "Impossible de créer le PDF : {error}",
        "person_1": "Importer la photo de la personne 1",
        "person_2": "Importer la photo de la personne 2",
        "caption_1": "Personne 1",
        "caption_2": "Personne 2",
        "generate": "✨ Créer le conte romantique",
        "upload_warning": "Veuillez importer les deux photos pour permettre l’analyse des personnages.",
        "spinner": "Création de cinq pages de poèmes et d’illustrations assorties …",
        "story_title": "📜 Votre livre de conte personnalisé",
        "fallback": "Le modèle {model} était temporairement indisponible. Le poème et l’illustration ont été créés avec un modèle de secours.",
        "incomplete_output": "Le modèle n’a pas fourni le poème demandé de 3 strophes AABB de 4 vers et une illustration pour une page. Veuillez réessayer.",
        "incomplete_poem_only": "Le modèle n’a pas fourni cinq poèmes de 3 strophes AABB de 4 vers chacun. Veuillez réessayer.",
        "quota_error": "Le quota de génération d’images Gemini de ce projet est épuisé (l’API indique une limite gratuite de 0). Vérifiez les limites du projet et la facturation. Un modèle de secours peut aussi échouer si son quota est épuisé.\n\nRemarque : l’API indique que vous pouvez réessayer dans {retry_delay}.",
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
        "continue_without_image": "Continuar sin generar imagen",
        "poem_only_spinner": "Creando el poema sin generar una imagen …",
        "poem_only_error": "No se pudo crear el poema sin imagen: {error}",
        "cloudflare_fallback": "Gemini no está disponible. Se intentará usar Cloudflare como alternativa.",
        "cloudflare_image_error": "Cloudflare creó el poema, pero no pudo generar una imagen: {error} Puedes continuar sin imagen.",
        "some_illustrations_missing": "No se pudo generar al menos una ilustración. Usa el botón de abajo para continuar sin imágenes.",
        "cloudflare_error": "El recurso alternativo de Cloudflare también falló: {error}",
        "cloudflare_auth_error": "Cloudflare rechazó la autenticación. Comprueba el ID de cuenta y crea un token de API de Workers AI en el panel de Cloudflare, en Workers AI. Un token creado manualmente necesita los permisos «Workers AI - Read» y «Workers AI - Edit». Sustituye CLOUDFLARE_ACCOUNT_ID y CLOUDFLARE_API_TOKEN en el archivo secrets.toml de esta aplicación.",
        "cloudflare_auth_docs": "Guía de Cloudflare: crear un token de API de Workers AI",
        "cloudflare_license_notice": "Cloudflare exige aceptar una licencia y una política de uso para este modelo de visión. Estas condiciones incluyen declarar que el usuario no reside en la UE y que la empresa no tiene allí su sede principal. Si no es tu caso, no aceptes las condiciones. El modelo de visión alternativo de Cloudflare ya se ha cambiado.",
        "cloudflare_vision_docs": "Información sobre el modelo de visión alternativo de Cloudflare",
        "without_illustration": "El PDF se creará sin ilustración generada.",
        "pdf_error": "No se pudo crear el PDF: {error}",
        "person_1": "Subir foto de la persona 1",
        "person_2": "Subir foto de la persona 2",
        "caption_1": "Persona 1",
        "caption_2": "Persona 2",
        "generate": "✨ Crear cuento romántico",
        "upload_warning": "Sube ambas fotos para poder analizar a los personajes.",
        "spinner": "Creando cinco páginas de poemas e ilustraciones a juego …",
        "story_title": "📜 Tu cuento personalizado",
        "fallback": "El modelo {model} no estaba disponible temporalmente. El poema y la ilustración se crearon con un modelo alternativo.",
        "incomplete_output": "El modelo no devolvió el poema solicitado de 3 estrofas AABB de 4 versos y una ilustración para una página. Inténtalo de nuevo.",
        "incomplete_poem_only": "El modelo no devolvió cinco poemas de 3 estrofas AABB de 4 versos cada uno. Inténtalo de nuevo.",
        "quota_error": "Se ha agotado la cuota de generación de imágenes de Gemini para este proyecto (la API indica un límite gratuito de 0). Comprueba los límites del proyecto y la facturación. Un modelo alternativo también puede fallar si ha agotado su cuota.\n\nAviso: la API indica que puedes volver a intentarlo en {retry_delay}.",
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
        "continue_without_image": "Continua senza generare immagini",
        "poem_only_spinner": "Creazione della poesia senza generare immagini …",
        "poem_only_error": "Impossibile creare la poesia senza immagini: {error}",
        "cloudflare_fallback": "Gemini non è disponibile. Verrà provato Cloudflare come alternativa.",
        "cloudflare_image_error": "Cloudflare ha creato la poesia, ma non è riuscito a generare un’immagine: {error} Puoi continuare senza immagine.",
        "some_illustrations_missing": "Non è stato possibile creare almeno un’illustrazione. Usa il pulsante qui sotto per continuare senza immagini.",
        "cloudflare_error": "Anche il fallback Cloudflare non è riuscito: {error}",
        "cloudflare_auth_error": "Cloudflare ha rifiutato l’autenticazione. Controlla l’ID account e crea un token API Workers AI nel dashboard Cloudflare, nella sezione Workers AI. Un token creato manualmente richiede le autorizzazioni «Workers AI - Read» e «Workers AI - Edit». Sostituisci CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN nel file secrets.toml di questa app.",
        "cloudflare_auth_docs": "Guida Cloudflare: crea un token API Workers AI",
        "cloudflare_license_notice": "Cloudflare richiede l’accettazione di una licenza e di una policy d’uso per questo modello visivo. Queste condizioni includono la dichiarazione che l’utente non è residente nell’UE e che l’azienda non vi ha la sede principale. Se non è il tuo caso, non accettare le condizioni. Il modello visivo alternativo di Cloudflare è stato sostituito.",
        "cloudflare_vision_docs": "Informazioni sul modello visivo alternativo Cloudflare",
        "without_illustration": "Il PDF sarà creato senza illustrazione generata.",
        "pdf_error": "Impossibile creare il PDF: {error}",
        "person_1": "Carica la foto della persona 1",
        "person_2": "Carica la foto della persona 2",
        "caption_1": "Persona 1",
        "caption_2": "Persona 2",
        "generate": "✨ Genera la fiaba romantica",
        "upload_warning": "Carica entrambe le foto per consentire l’analisi dei personaggi.",
        "spinner": "Creazione di cinque pagine di poesie e illustrazioni abbinate …",
        "story_title": "📜 La tua fiaba personalizzata",
        "fallback": "Il modello {model} non era temporaneamente disponibile. La poesia e l’illustrazione sono state create con un modello alternativo.",
        "incomplete_output": "Il modello non ha restituito la poesia richiesta di 3 strofe AABB da 4 versi e un’illustrazione per una pagina. Riprova.",
        "incomplete_poem_only": "Il modello non ha restituito cinque poesie di 3 strofe AABB da 4 versi ciascuna. Riprova.",
        "quota_error": "La quota di generazione immagini Gemini per questo progetto è esaurita (l’API indica un limite gratuito pari a 0). Controlla i limiti del progetto e la fatturazione. Anche un modello alternativo può non funzionare se la sua quota è esaurita.\n\nNota: l’API indica che puoi riprovare tra {retry_delay}.",
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


def poem_rhyme_key(line: str, language_code: str) -> str:
    """Approximate a line's rhyme ending for the supported European languages."""
    words = re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", line.casefold())
    if not words:
        return ""
    word = "".join(
        char
        for char in unicodedata.normalize("NFKD", words[-1])
        if not unicodedata.combining(char)
    )
    word = re.sub(r"[^a-z]", "", word)
    if language_code == "fr":
        while len(word) > 2 and word.endswith(("s", "x")):
            word = word[:-1]
        if word.endswith(("ant", "ent", "ans", "and", "emps")):
            return "an"
    if language_code == "en" and word.endswith("ue"):
        return "ue"
    if language_code == "en" and len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    if language_code == "it" and word.endswith("ia"):
        return "ia"
    if language_code == "en" and len(word) > 1 and word.endswith("y") and word[-2] in "aeiou":
        return word[-2:]
    if word.endswith(("a", "e", "i", "o", "u")):
        if language_code == "fr":
            return word[-1]
        if language_code == "it":
            return word[-3:]
        if language_code == "es":
            return word[-2:]
    if language_code == "en" and word.endswith("y"):
        return "y"
    vowel_positions = [index for index, char in enumerate(word) if char in "aeiou"]
    if not vowel_positions:
        return ""
    last_vowel = vowel_positions[-1]
    start = last_vowel
    minimum_length = 3 if language_code == "it" else 2
    while start > 0 and len(word) - start < minimum_length:
        start -= 1
    return word[start:]


def poem_language_code(output_language: str) -> str:
    return OUTPUT_LANGUAGE_CODES.get(output_language.casefold(), "en")


def rhyme_examples_for_language(output_language: str) -> str:
    """Return language-specific rhyme examples for generation prompts."""
    examples = RHYME_EXAMPLES.get(
        poem_language_code(output_language),
        RHYME_EXAMPLES["en"],
    )
    return "; ".join(examples)


def aabb_rhyme_issues(poem: str, language_code: str) -> list[str]:
    """Describe adjacent line pairs that the spelling-based rhyme check rejects."""
    if not is_valid_poem(poem):
        return ["the poem does not have three four-line stanzas"]
    issues = []
    for stanza_number, stanza in enumerate(parse_poem_stanzas(poem), start=1):
        for pair_number, (first, second) in enumerate(
            ((stanza[0], stanza[1]), (stanza[2], stanza[3]))
        ):
            first_key = poem_rhyme_key(first, language_code)
            second_key = poem_rhyme_key(second, language_code)
            first_words = re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", first.casefold())
            second_words = re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", second.casefold())
            first_line_number = (stanza_number - 1) * 4 + pair_number * 2 + 1
            second_line_number = first_line_number + 1
            if not first_words or not second_words:
                issues.append(
                    f"stanza {stanza_number} has a line without a final word"
                )
            elif first_words[-1] == second_words[-1]:
                issues.append(
                    f"lines {first_line_number}/{second_line_number} repeat "
                    f"the end word '{first_words[-1]}'"
                )
            elif not first_key or first_key != second_key:
                issues.append(
                    f"lines {first_line_number}/{second_line_number} end with "
                    f"'{first_words[-1]}'/'{second_words[-1]}' "
                    f"(checked endings '{first_key}'/'{second_key}')"
                )
    return issues


def has_aabb_rhyme(poem: str, language_code: str) -> bool:
    """Check that each quatrain's two adjacent line pairs share rhyme endings."""
    return not aabb_rhyme_issues(poem, language_code)


def exact_rhyme_repair_instruction(output_language: str) -> str:
    """Map the verified example pairs to all six adjacent line pairs."""
    pairs = RHYME_EXAMPLES[poem_language_code(output_language)]
    assignments = "; ".join(
        f"line {index * 2 + 1} ends with {pair.split('/')[0]} and "
        f"line {index * 2 + 2} ends with {pair.split('/')[1]}"
        for index, pair in enumerate(pairs)
    )
    return (
        "For the next draft, use these exact end words, in this order, without "
        f"changing their spelling: {assignments}."
    )


def is_distinct_poem(poem: str, previous_poems: list[str]) -> bool:
    """Reject an exact or near-duplicate poem within the same generated book."""
    canonical = re.sub(r"\W+", " ", poem.casefold()).strip()
    if not canonical:
        return False
    return all(
        SequenceMatcher(
            None,
            canonical,
            re.sub(r"\W+", " ", previous.casefold()).strip(),
            autojunk=False,
        ).ratio()
        < 0.85
        for previous in previous_poems
    )


def derive_poem_title(poem: str) -> str:
    """Use the opening line as an incipit title for the book cover."""
    stanzas = parse_poem_stanzas(poem)
    if not stanzas or not stanzas[0]:
        raise ValueError("The first poem has no opening line for the cover title.")
    return stanzas[0][0].strip().rstrip(" .!?…")


def extract_cloudflare_poem_lines(poem: str) -> list[str]:
    """Extract poem lines and join wrapped continuations of numbered lines."""
    poem = re.sub(r"```(?:\w+)?\s*|\s*```", "", poem).strip()
    lines = []
    numbered_line_pattern = re.compile(
        r"^\s*(?:[-*•]\s*)?(?:\(?\d{1,2}[.)]\)?|\d{1,2}:)\s*(.*)$"
    )
    has_numbered_lines = any(
        numbered_line_pattern.match(line) for line in poem.splitlines()
    )
    stanza_label_pattern = re.compile(
        r"(?:\*\*)?stanza\s+\d+(?:\*\*)?:?", re.IGNORECASE
    )
    for raw_line in poem.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", raw_line).strip()
        if not line or stanza_label_pattern.fullmatch(line):
            continue
        numbered_match = numbered_line_pattern.match(line)
        if numbered_match:
            lines.append(numbered_match.group(1).strip().strip("*").strip())
        elif has_numbered_lines:
            if lines:
                lines[-1] = f"{lines[-1]} {line}".strip()
        else:
            line = re.sub(r"^\s*(?:[-*•]\s+)", "", line)
            line = line.strip().strip("*").strip()
            if line:
                lines.append(line)

    return lines


def normalize_cloudflare_poem(poem: str) -> str:
    """Normalize common list and stanza formatting while enforcing 12 poem lines."""
    poem_lines = extract_cloudflare_poem_lines(poem)
    if len(poem_lines) != 12:
        return ""
    return "\n\n".join(
        "\n".join(poem_lines[index : index + 4])
        for index in range(0, 12, 4)
    )


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

    Safe end-rhyme examples in {output_language}: {rhyme_examples_for_language(output_language)}.
    Use different end words for every line and prefer these pairs when they fit the story.
    Other pairs are acceptable only when their final spoken sounds clearly rhyme.
    Return a unique romantic poem in {output_language} consisting of exactly 3 stanzas,
    exactly 4 lines per stanza, and exactly 12 lines total. Use clear AABB end rhymes in
    every stanza: the final words of lines 1 and 2 must rhyme, as must lines 3 and 4.
    Choose simple, unmistakable rhyme pairs. Separate stanzas with one blank line.
    Make this page's poem substantially different from every previous poem. Do not reuse
    any previous line, image, event, or distinctive phrase. Follow this page's story direction
    with its own concrete scene and advance the overall story.
    Return only the poem, with no title, numbering, headings, explanations, or other text.

    Also generate exactly one finished watercolor children's-book illustration for this page.
    Show the same two main characters in a scene appropriate to this page in the story.
    The output must be an actual image without text, letters, captions, or watermark.
    """


class CloudflareAuthenticationError(RuntimeError):
    pass


def cloudflare_api_request(
    model: str, payload: dict[str, object]
) -> tuple[bytes, str]:
    """Call a Workers AI model without exposing credentials in errors."""
    account_id = st.secrets.get("CLOUDFLARE_ACCOUNT_ID")
    api_token = st.secrets.get("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        raise RuntimeError(
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must be configured "
            "in this app's .streamlit/secrets.toml."
        )

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{quote(str(account_id), safe='')}/ai/run/{quote(model, safe='@/-')}"
    )
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except HTTPError as e:
        if e.code == 401:
            raise CloudflareAuthenticationError(
                "Cloudflare Workers AI rejected the configured credentials."
            ) from e
        response_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Cloudflare Workers AI returned HTTP {e.code}: {response_body[:1000]}"
        ) from e


def prepare_cloudflare_vision_image(img1: Image.Image, img2: Image.Image) -> bytes:
    """Create one compact side-by-side image for the vision model input."""
    tile_size = (512, 512)
    collage = Image.new("RGB", (tile_size[0] * 2, tile_size[1]), "white")
    for index, source in enumerate((img1, img2)):
        image = ImageOps.contain(source.convert("RGB"), tile_size)
        x = index * tile_size[0] + (tile_size[0] - image.width) // 2
        y = (tile_size[1] - image.height) // 2
        collage.paste(image, (x, y))

    image_buffer = BytesIO()
    collage.save(image_buffer, format="JPEG", quality=85, optimize=True)
    return image_buffer.getvalue()


class IncompleteGeneratedPageError(RuntimeError):
    pass


def cloudflare_generate_poem_and_image_prompt(
    img1: Image.Image,
    img2: Image.Image,
    style: str,
    output_language: str,
    page_number: int,
    previous_poems: list[str],
    revision_feedback: str | None = None,
) -> tuple[str, str]:
    """Use Cloudflare vision to write one story page and describe its image."""
    previous_context = "\n\n".join(previous_poems)
    prompt = f"""
    Analyze both people in the attached side-by-side photos. Preserve their visible hair, glasses,
    clothing, and other distinguishing features in the illustration description.

    Create page {page_number} of {CAMEO_PAGE_COUNT} in a romantic fairytale photo book in this style:
    "{style}". Story direction: {page_story_context(page_number)}
    Continue consistently from these previous page poems:
    {previous_context or "[This is the opening page.]"}

    {f"IMPORTANT CORRECTION FOR THIS RETRY: {revision_feedback}" if revision_feedback else ""}

    Write a unique romantic poem in {output_language}: exactly 12 numbered lines.
    In the POEM section, put exactly one complete verse on each physical line,
    numbered 1. through 12. Do not wrap a verse onto another line or add prose.
    Put one blank line only after lines 4 and 8. Follow this exact format:
    1. [first verse]
    2. [second verse]
    3. [third verse]
    4. [fourth verse]

    5. [fifth verse]
    6. [sixth verse]
    7. [seventh verse]
    8. [eighth verse]

    9. [ninth verse]
    10. [tenth verse]
    11. [eleventh verse]
    12. [twelfth verse]
    Safe end-rhyme examples in {output_language}: {rhyme_examples_for_language(output_language)}.
    Prefer these pairs when they fit the story; other pairs are acceptable only when
    their final spoken sounds clearly rhyme. Never repeat an end word.
    Every stanza must have strong, unmistakable AABB end rhymes. The final sounds of
    lines 1 and 2 must rhyme, as must lines 3 and 4. Before answering, check each of
    the six line pairs yourself and rewrite any pair that does not rhyme naturally.
    Do not use the same end word twice as a substitute for a rhyme.
    Make the poem and scene substantially different from every previous page. Do not reuse
    any previous line, event, or distinctive phrase, and advance this page's story direction.

    Then write one concise prompt for a matching watercolor children's-book illustration of the same
    two recognizable people acting out this page's story scene. Request no text, lettering, captions,
    or watermark.

    Use these exact section headings, each on its own line. Do not omit either section.
    Keep the numbering 1 through 12 on poem lines only:
    POEM:
    [the three stanzas]

    IMAGE_PROMPT:
    [the visual description for the image generator]

    The image prompt must describe a complete scene with both people, their visible features,
    the setting, and the requested art style. Do not put the image prompt inside the poem.
    """
    response_data, content_type = cloudflare_api_request(
        CLOUDFLARE_VISION_MODEL,
        {
            "prompt": prompt,
            "image": list(prepare_cloudflare_vision_image(img1, img2)),
            "max_tokens": 900,
        },
    )
    if "json" not in content_type.lower():
        raise RuntimeError("Cloudflare returned an unexpected text response format.")
    envelope = json.loads(response_data)
    if not envelope.get("success", False):
        errors_text = "; ".join(
            str(error.get("message", error))
            if isinstance(error, dict)
            else str(error)
            for error in envelope.get("errors", [])
        )
        raise RuntimeError(errors_text or "Cloudflare text generation failed.")

    result = envelope.get("result") or {}
    response_text = result.get("response") or result.get("description", "")
    section_pattern = re.compile(
        r"(?im)^[ \t]*(?:[#>*-][ \t]*)?(?:\*\*)?"
        r"(POEM|IMAGE(?:[\s_-]*PROMPT)?|ILLUSTRATION(?:[\s_-]*PROMPT)?|"
        r"IMAGE[\s_-]*DESCRIPTION|VISUAL[\s_-]*DESCRIPTION)"
        r"[ \t]*:?(?:\*\*)?[ \t]*:?[ \t]*(.*)$"
    )
    matches = list(section_pattern.finditer(response_text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = re.sub(r"[\s_-]+", " ", match.group(1).upper()).strip()
        content_start = match.end()
        content_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(response_text)
        )
        content = "\n".join(
            part
            for part in (
                match.group(2).strip(),
                response_text[content_start:content_end].strip(),
            )
            if part
        ).strip()
        sections[label] = content

    poem = sections.get("POEM", response_text).strip()
    poem_lines = extract_cloudflare_poem_lines(poem)
    poem = normalize_cloudflare_poem(poem) or "\n".join(poem_lines)
    image_prompt = next(
        (
            section
            for label, section in sections.items()
            if label != "POEM" and section
        ),
        "",
    )
    if not image_prompt:
        image_prompt = (
            "Create one finished watercolor children's-book illustration for a romantic "
            f"fairytale, in the style '{style}'. Show the same two people together in a "
            f"scene inspired by this story moment: {page_story_context(page_number)} "
            f"Visual inspiration from the poem: {poem.replace(chr(10), ' ')} "
            "Use a magical, expressive setting; no text, lettering, captions, or watermark."
        )
    return poem, image_prompt[:1800]


def generate_distinct_cloudflare_poem(
    img1: Image.Image,
    img2: Image.Image,
    style: str,
    output_language: str,
    page_number: int,
    previous_poems: list[str],
) -> tuple[str, str]:
    """Retry Cloudflare text generation until the poem is valid and distinct."""
    revision_feedback = None
    language_code = poem_language_code(output_language)
    last_failure = "unknown validation failure"
    for _ in range(MAX_CLOUDFLARE_POEM_ATTEMPTS):
        poem, image_prompt = cloudflare_generate_poem_and_image_prompt(
            img1,
            img2,
            style,
            output_language,
            page_number,
            previous_poems,
            revision_feedback,
        )
        if not is_valid_poem(poem):
            candidate_line_count = sum(
                len(stanza) for stanza in parse_poem_stanzas(poem)
            )
            last_failure = (
                f"the poem parser found {candidate_line_count} candidate verse lines; "
                "it must find exactly 12, numbered 1. through 12., with one "
                "complete verse on each physical line and blank lines only after "
                "lines 4 and 8"
            )
        elif not has_aabb_rhyme(poem, language_code):
            last_failure = (
                "the app's spelling-based rhyme check rejected: "
                f"{'; '.join(aabb_rhyme_issues(poem, language_code))}. "
                f"{exact_rhyme_repair_instruction(output_language)}"
            )
        elif not is_distinct_poem(poem, previous_poems):
            last_failure = (
                "the poem is too similar to an earlier page; use new wording and "
                "a different event from this page's story direction"
            )
        else:
            return poem, image_prompt
        revision_feedback = (
            f"The previous draft was rejected because {last_failure}. Do not repeat "
            "that draft. Correct the issue and check all 12 lines before returning."
        )
    raise IncompleteGeneratedPageError(
        f"Cloudflare did not return a distinct, valid AABB poem after "
        f"{MAX_CLOUDFLARE_POEM_ATTEMPTS} attempts for page {page_number}."
        f" Last validation issue: {last_failure}."
    )


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
        or not has_aabb_rhyme(poem, poem_language_code(output_language))
        or not is_distinct_poem(poem, previous_poems)
    ):
        raise IncompleteGeneratedPageError(
            f"Gemini did not return a distinct 12-line poem with three AABB-rhyming "
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


def cloudflare_generate_image(image_prompt: str) -> bytes:
    """Generate a PNG illustration using Cloudflare's Workers AI model."""
    response_data, content_type = cloudflare_api_request(
        CLOUDFLARE_IMAGE_MODEL,
        {
            "prompt": image_prompt,
            "negative_prompt": "text, letters, words, captions, watermark",
            "width": 768,
            "height": 1024,
            "num_steps": 4,
        },
    )
    if "json" in content_type.lower():
        envelope = json.loads(response_data)
        if not envelope.get("success", False):
            errors_text = "; ".join(
                str(error.get("message", error))
                if isinstance(error, dict)
                else str(error)
                for error in envelope.get("errors", [])
            )
            raise RuntimeError(errors_text or "Cloudflare image generation failed.")
        encoded_image = (envelope.get("result") or {}).get("image")
        if not encoded_image:
            raise RuntimeError("Cloudflare returned no generated image.")
        image_data = base64.b64decode(encoded_image)
    else:
        image_data = response_data

    try:
        with Image.open(BytesIO(image_data)) as image:
            image.verify()
    except Exception as e:
        raise RuntimeError("Cloudflare returned invalid image data.") from e
    return image_data


def is_cloudflare_vision_license_error(error: Exception) -> bool:
    """Detect errors that require a user to accept the vision model terms."""
    message = str(error).lower()
    return any(term in message for term in ("license", "licence", "acceptable use"))


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
        for key in (
            "generated_pages",
            "generated_language_code",
            "cloudflare_fallback_needs_choice",
        ):
            st.session_state.pop(key, None)

        with st.spinner(text["spinner"]):
            try:
                client = genai.Client(api_key=api_key)
                gemini_init_error = None
            except Exception as e:
                client = None
                gemini_init_error = e
            generated_pages: list[tuple[str, bytes | None]] = []
            previous_poems = []
            cloudflare_used = False
            generation_error = None
            quota_warning_shown = False

            for page_number in range(1, CAMEO_PAGE_COUNT + 1):
                try:
                    try:
                        if client is None:
                            raise IncompleteGeneratedPageError(
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
                        if e.code not in GEMINI_FALLBACK_ERROR_CODES:
                            raise
                        if e.code == 429 and not quota_warning_shown:
                            quota_warning_shown = True
                            retry_delay = format_retry_delay(e) or text["retry_later"]
                            st.error(
                                text["quota_error"].format(retry_delay=retry_delay)
                            )
                        raise IncompleteGeneratedPageError(
                            f"Gemini is unavailable for page {page_number}."
                        ) from e

                except IncompleteGeneratedPageError:
                    cloudflare_used = True
                    if page_number == 1:
                        st.info(text["cloudflare_fallback"])
                    try:
                        poem, image_prompt = generate_distinct_cloudflare_poem(
                            img1,
                            img2,
                            stil,
                            text["output_language"],
                            page_number,
                            previous_poems,
                        )
                        try:
                            image_data = cloudflare_generate_image(image_prompt)
                        except Exception as image_error:
                            image_data = None
                            st.error(
                                text["cloudflare_image_error"].format(
                                    error=image_error
                                )
                            )
                    except Exception as cloudflare_error:
                        generation_error = cloudflare_error
                        if is_cloudflare_vision_license_error(cloudflare_error):
                            st.info(text["cloudflare_license_notice"])
                            st.markdown(
                                f"[{text['cloudflare_vision_docs']}]"
                                f"({CLOUDFLARE_VISION_DOC_URL})"
                            )
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
                if cloudflare_used:
                    if isinstance(generation_error, CloudflareAuthenticationError):
                        st.error(text["cloudflare_auth_error"])
                        st.markdown(
                            f"[{text['cloudflare_auth_docs']}]"
                            f"({CLOUDFLARE_REST_API_DOC_URL})"
                        )
                    else:
                        st.error(text["cloudflare_error"].format(error=generation_error))
                else:
                    st.error(text["error"].format(error=generation_error))
            elif len(generated_pages) == CAMEO_PAGE_COUNT:
                st.session_state.generated_pages = generated_pages
                st.session_state.generated_language_code = language_code
                st.session_state.cloudflare_fallback_needs_choice = any(
                    image_data is None for _, image_data in generated_pages
                )

if (
    st.session_state.get("cloudflare_fallback_needs_choice")
    and "generated_pages" in st.session_state
    and st.button(text["continue_without_image"], type="secondary")
):
    st.session_state.generated_pages = [
        (poem, None) for poem, _ in st.session_state.generated_pages
    ]
    st.session_state.cloudflare_fallback_needs_choice = False
    st.rerun()

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

    if all(image_data is None for _, image_data in pages):
        st.info(generated_text["without_illustration"])
    elif any(image_data is None for _, image_data in pages):
        st.info(generated_text["some_illustrations_missing"])

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