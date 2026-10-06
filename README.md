# Liebeslegende

A multilingual Streamlit app that creates a five-page fairytale love-poem book from two uploaded photos. Each illustrated page contains a 12-line poem in three AABB-rhyming stanzas. The generated book is available as an A4 PDF with a cover.

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create `.streamlit/secrets.toml` with your own API credentials:

   ```toml
   GEMINI_API_KEY = "your-gemini-api-key"
   CLOUDFLARE_ACCOUNT_ID = "your-cloudflare-account-id"
   CLOUDFLARE_API_TOKEN = "your-cloudflare-api-token"
   ```

4. Start the app:

   ```powershell
   streamlit run app.py
   ```

The local secrets file is intentionally excluded from Git. Never commit API keys or tokens. For Streamlit Community Cloud, add the same settings in the app's **Settings → Secrets** page.

Gemini is used as the primary text-and-image generator. Cloudflare Workers AI is used as a fallback when Gemini is unavailable. Both services need valid credentials and may have separate quotas and model availability.
