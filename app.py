import streamlit as st
import pandas as pd
import sqlite3
import re
import hashlib
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract
import fitz  # PyMuPDF
import io

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "land_records.db"

st.set_page_config(page_title="Land Record Digitization & Validation", page_icon="📄", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
.hero {padding: 1.2rem 1.4rem; border-radius: 14px; background: linear-gradient(120deg,#15324b,#176c78); color: white; margin-bottom: 1rem;}
.hero h1 {color:white; margin-bottom:.25rem;}
.small-note {font-size: .88rem; color: #5b6570;}
</style>
<div class="hero">
<h1>Intelligent Land Record Digitization & Validation System</h1>
<p>OCR • Structured extraction • Validation • Human review • Searchable records</p>
</div>
""", unsafe_allow_html=True)

st.warning("Academic prototype only. Use authorized sample/redacted documents. Do not upload sensitive real land records to a public demo. OCR output must be checked by an authorized human; this app does not determine legal ownership.")

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT UNIQUE,
            filename TEXT,
            uploaded_at TEXT,
            owner_name TEXT,
            village TEXT,
            survey_number TEXT,
            land_area TEXT,
            raw_text TEXT,
            validation_status TEXT,
            validation_issues TEXT,
            review_status TEXT
        )
    """)
    conn.commit()
    return conn

def render_pdf_pages(file_bytes, max_pages=10):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    for page in doc[:max_pages]:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        images.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
    return images, len(doc)

def prep_image(img):
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = img.filter(ImageFilter.SHARPEN)
    return img

def run_ocr(images, language):
    outputs = []
    for img in images:
        cleaned = prep_image(img)
        outputs.append(pytesseract.image_to_string(cleaned, lang=language, config="--psm 6"))
    return "\n\n--- PAGE BREAK ---\n\n".join(outputs).strip()

def first_match(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip(" :\t-")
    return ""

def extract_fields(text):
    # Pattern-based extraction is deliberately conservative; user must verify all values.
    owner = first_match([
        r"(?:owner(?:'s)?\s*name|name\s*of\s*owner|khatedar(?:\s*name)?|bhumiswami(?:\s*name)?|भूमिस्वामी(?:\s*का\s*नाम)?|खातेदार(?:\s*का\s*नाम)?|मालिक(?:\s*का\s*नाम)?)\s*[:\-]?\s*([^\n]{2,80})"
    ], text)
    village = first_match([
        r"(?:village|gram|ग्राम|गाँव|गांव)\s*[:\-]?\s*([^\n]{2,60})"
    ], text)
    survey = first_match([
        r"(?:survey(?:\s*no\.?|\s*number)?|plot(?:\s*no\.?|\s*number)?|khasra(?:\s*no\.?|\s*number)?|खसरा(?:\s*नंबर|\s*क्रमांक|\s*संख्या)?|सर्वे(?:\s*नंबर|\s*क्रमांक|\s*संख्या)?)\s*[:\-]?\s*([A-Za-z0-9./\-]{1,30})"
    ], text)
    area = first_match([
        r"(?:land\s*area|area|रकबा|क्षेत्रफल)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?\s*(?:hectare|hectares|ha|acre|acres|एकड़|हेक्टेयर|बीघा)?)"
    ], text)
    return {"owner_name": owner, "village": village, "survey_number": survey, "land_area": area}

def validate_record(fields):
    issues = []
    required = {
        "Owner name": fields.get("owner_name", ""),
        "Village": fields.get("village", ""),
        "Survey/plot number": fields.get("survey_number", ""),
        "Land area": fields.get("land_area", "")
    }
    for label, value in required.items():
        if not str(value).strip():
            issues.append(f"Missing or not detected: {label}")
    survey = str(fields.get("survey_number", "")).strip()
    if survey and not re.fullmatch(r"[A-Za-z0-9./\-]{1,30}", survey):
        issues.append("Survey/plot number has an unusual format")
    area = str(fields.get("land_area", "")).strip()
    if area and not re.search(r"\d", area):
        issues.append("Land area does not contain a numeric value")
    return issues

conn = db()
tab_upload, tab_records, tab_about = st.tabs(["📤 Upload & Process", "🗂️ Records Dashboard", "ℹ️ About / Demo Guide"])

with tab_upload:
    st.subheader("1. Upload a land-record document")
    uploaded = st.file_uploader("Choose PDF, JPG, JPEG or PNG", type=["pdf", "jpg", "jpeg", "png"])
    lang_choice = st.selectbox("OCR language", ["English", "Hindi + English"], index=0)
    lang_code = "eng" if lang_choice == "English" else "hin+eng"
    if uploaded:
        file_bytes = uploaded.getvalue()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        st.caption(f"File: {uploaded.name} • Size: {len(file_bytes)/1024:.1f} KB")
        if uploaded.type == "application/pdf" or uploaded.name.lower().endswith(".pdf"):
            try:
                images, page_count = render_pdf_pages(file_bytes)
                st.info(f"PDF has {page_count} page(s). This prototype processes the first {len(images)} page(s), up to 10.")
            except Exception as e:
                images = []
                st.error(f"Could not read PDF: {e}")
        else:
            try:
                images = [Image.open(io.BytesIO(file_bytes)).convert("RGB")]
            except Exception as e:
                images = []
                st.error(f"Could not read image: {e}")

        if images:
            with st.expander("Preview first page"):
                st.image(images[0], use_container_width=True)
            if st.button("Run OCR & Validate", type="primary"):
                try:
                    with st.spinner("Reading document and checking fields..."):
                        raw_text = run_ocr(images, lang_code)
                    fields = extract_fields(raw_text)
                    issues = validate_record(fields)
                    st.session_state["current_result"] = {
                        "file_hash": file_hash,
                        "filename": uploaded.name,
                        "raw_text": raw_text,
                        **fields,
                        "issues": issues
                    }
                except pytesseract.TesseractNotFoundError:
                    st.error("OCR engine is not installed. Check packages.txt and requirements.txt, then redeploy.")
                except Exception as e:
                    st.error(f"Processing failed: {e}")

    result = st.session_state.get("current_result")
    if result:
        st.subheader("2. Review extracted fields")
        st.caption("OCR extraction is best-effort. Correct each field by comparing it with the original document.")
        with st.form("review_form"):
            c1, c2 = st.columns(2)
            with c1:
                owner_name = st.text_input("Owner name", value=result["owner_name"])
                village = st.text_input("Village", value=result["village"])
            with c2:
                survey_number = st.text_input("Survey / plot number", value=result["survey_number"])
                land_area = st.text_input("Land area (keep unit)", value=result["land_area"])
            review_status = st.selectbox("Review status", ["Pending human review", "Reviewed - needs correction", "Reviewed - fields checked"])
            submitted = st.form_submit_button("Save record to database", type="primary")
        if submitted:
            fields = {"owner_name": owner_name.strip(), "village": village.strip(),
                      "survey_number": survey_number.strip(), "land_area": land_area.strip()}
            issues = validate_record(fields)
            status = "Needs review" if issues else "Basic checks passed - human review still required"
            try:
                conn.execute("""
                    INSERT INTO records
                    (file_hash, filename, uploaded_at, owner_name, village, survey_number, land_area,
                     raw_text, validation_status, validation_issues, review_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (result["file_hash"], result["filename"], datetime.now().isoformat(timespec="seconds"),
                      fields["owner_name"], fields["village"], fields["survey_number"], fields["land_area"],
                      result["raw_text"], status, "\n".join(issues), review_status))
                conn.commit()
                st.success("Record saved. Open the Records Dashboard to search, review and export it.")
                st.session_state.pop("current_result", None)
            except sqlite3.IntegrityError:
                st.error("This exact file has already been saved (duplicate file hash). Check the Records Dashboard.")
        with st.expander("View raw OCR text"):
            st.text_area("Extracted text", value=result["raw_text"], height=220)
        if result["issues"]:
            st.error("Validation flags detected:")
            for issue in result["issues"]:
                st.write(f"• {issue}")
        else:
            st.success("No basic validation flags detected. This is not proof of legal or factual correctness.")

with tab_records:
    st.subheader("Saved records")
    data = pd.read_sql_query("SELECT * FROM records ORDER BY id DESC", conn)
    if data.empty:
        st.info("No records saved yet. Upload a sample document in the first tab.")
    else:
        search = st.text_input("Search by owner, village or survey/plot number")
        if search:
            mask = data[["owner_name", "village", "survey_number", "filename"]].fillna("").astype(str).apply(
                lambda col: col.str.contains(search, case=False, regex=False)
            ).any(axis=1)
            shown = data[mask]
        else:
            shown = data
        m1, m2, m3 = st.columns(3)
        m1.metric("Total saved records", len(data))
        m2.metric("Needs review", int(data["validation_status"].fillna("").str.contains("Needs review").sum()))
        m3.metric("Reviewed", int(data["review_status"].fillna("").str.startswith("Reviewed").sum()))
        display_cols = ["id", "filename", "uploaded_at", "owner_name", "village", "survey_number", "land_area", "validation_status", "review_status"]
        st.dataframe(shown[display_cols], use_container_width=True, hide_index=True)
        csv = shown[display_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button("Download visible records as CSV", data=csv, file_name="land_records_export.csv", mime="text/csv")
        selected_id = st.selectbox("View full record ID", options=shown["id"].tolist() if not shown.empty else [])
        if selected_id:
            row = data[data["id"] == selected_id].iloc[0]
            st.markdown("**Validation issues**")
            st.write(row["validation_issues"] or "No basic validation flags.")
            with st.expander("Raw OCR text"):
                st.text_area("OCR text", value=row["raw_text"] or "", height=180, key=f"raw_{selected_id}")
            st.caption("To correct saved data, use the upload/review flow for a new corrected version. This prototype preserves saved records instead of silently overwriting them.")

with tab_about:
    st.subheader("What this prototype does")
    st.markdown("""
- Accepts PDF and image uploads.
- Uses Tesseract OCR to read printed text (Hindi + English option requires Hindi language data).
- Attempts conservative pattern-based extraction for owner name, village, survey/plot number and land area.
- Flags missing fields and basic format problems.
- Lets a user correct extracted fields before saving.
- Stores saved records in a local SQLite database and supports search/CSV export.

**What it does not do**
- It does not verify land ownership or legal validity.
- It does not guarantee OCR accuracy, especially for handwriting, stamps, old scans or unusual layouts.
- It is not yet connected to any government land-record database or official API.
- The SQLite database on a hosted demo may be temporary and is not a production storage solution.
    """)
    st.subheader("Suggested live demo")
    st.markdown("""
1. Use a sample or redacted land-record page.
2. Upload it and run OCR.
3. Compare extracted values against the scan.
4. Correct any mistakes and save the record.
5. Open the dashboard, search for the record and export CSV.
    """)
    st.subheader("Team")
    st.write("Komal Kushwaha (0501AD231035) • Dushyant Sahu (0501AD231025) • Lakshya Yaduwanshi (0501AD231036) • Simran Gour (0501AD231060)")
    st.caption("Problem statement: SIH26018 • Software • Smart Automation")
