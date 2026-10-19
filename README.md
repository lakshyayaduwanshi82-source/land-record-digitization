# Intelligent Land Record Digitization & Validation System

A working academic prototype for document upload, OCR, field extraction, basic validation, manual review, SQLite storage, search and CSV export.

## Run locally
1. Install Python 3.10+.
2. Install the Tesseract OCR system package and English/Hindi language packs for your operating system.
3. In a terminal, run:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. Open the local URL printed by Streamlit.

## Deploy as a live web demo
1. Create a GitHub repository and upload `app.py`, `requirements.txt`, and `packages.txt`.
2. In Streamlit Community Cloud, create an app from that repository and choose `app.py` as the main file.
3. Wait for deployment. The `packages.txt` file installs the Tesseract system OCR packages.
4. Test with a sample/redacted document.

## Important limits
- This is a prototype, not a government-integrated production system.
- OCR and extraction are best-effort and must be checked against the original.
- Never use OCR output alone to determine ownership or legal rights.
- Do not upload sensitive real land records to a public demo.
- Hosted local SQLite storage may not be persistent; use approved persistent storage before any real deployment.
