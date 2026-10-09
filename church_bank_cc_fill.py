import io
import os
import re
import time
import logging
import requests
import pandas as pd

from tqdm import tqdm

import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes

log = logging.getLogger(__name__)


CC_ACCOUNTS_PAGE = (
    "https://register-of-charities.charitycommission.gov.uk"
    "/en/charity-search/-/charity-details/{regno}/accounts-and-annual-returns"
    "?_uk_gov_ccew_onereg_charitydetails_web_portlet_CharityDetailsPortlet_organisationNumber={regno}"
)

OCR_DPI = 200
PDF_RETRY_DELAY = 1.0  # seconds to wait between PDF fetches to avoid overwhelming the server

POPPLER_PATH = r"C:\Users\stefa\Downloads\Release-26.02.0-0\poppler-26.02.0\Library\bin"
TESSERACT_PATH = r"C:\Users\stefa\AppData\Local\Programs\Tesseract-OCR"
os.environ["PATH"] = os.environ["PATH"] + os.pathsep + TESSERACT_PATH



BANK_KEYWORDS = [
    r"principal\s+bank(?:ers?)?",
    r"bank(?:ers?)?\s+(?:is|are|:)",
    r"banking\s+with",
    r"banked\s+with",
    r"account(?:s)?\s+(?:are\s+)?held\s+with",
    r"financial\s+institution",
]
BANK_KEYWORD_RE = re.compile("|".join(BANK_KEYWORDS), re.IGNORECASE)
 
KNOWN_BANKS = [
    "Barclays", "HSBC", "NatWest", "National Westminster", "Lloyds", "Santander", "Halifax",
    "TSB", "Metro Bank", "Nationwide", "Virgin Money", "Co-operative Bank",
    "Triodos", "CAF Bank", "Unity Trust", "Charity Bank", "Handelsbanken",
    "Yorkshire Bank", "Bank of Scotland", "Ulster Bank", "Clydesdale",
    "Standard Chartered", "Starling", "Monzo", "Tide",
]
BANK_NAME_RE = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in KNOWN_BANKS) + r")\b",
    re.IGNORECASE
)

# Compiled pattern to find the accounts-download-link anchor tags.
# The href on these links is a CC portal URL (not a direct .pdf URL) — the server
# redirects to the actual PDF when followed.
ACCOUNTS_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*accounts-download-link[^"]*"[^>]+href="([^"]+)"',
    re.IGNORECASE,
)
 

def get_accounts_pdf_url(regno: str, session: requests.Session) -> str | None:
    """
    Fetch the charity's accounts-and-annual-returns page and return the download
    URL for the most recently submitted accounts PDF.
 
    The page contains a table of annual returns and accounts rows in descending
    date order. Each "Accounts and TAR" row that has a submitted document contains
    an <a class="accounts-download-link"> anchor. We take the first such link
    (i.e. the most recent), which the CC server will redirect to the actual PDF.
 
    Returns None if the page cannot be fetched or no download links are present
    (e.g. the charity has never submitted accounts, or all years are "Not required").
    """
    url = CC_ACCOUNTS_PAGE.format(regno=regno)
    try:
        resp = session.get(url, timeout=5)
        resp.raise_for_status()
    except Exception as e:
        log.error(f" Could not fetch accounts page for regno={regno}: {e}")
        return None
 
    # The rows are already in descending date order, so the first match is
    # the most recent submitted accounts.
    match = ACCOUNTS_LINK_RE.search(resp.text)
    if match:
        href = match.group(1)
        # Unescape HTML entities (e.g. &amp; → &) that appear in the href
        href = href.replace("&amp;", "&")
        log.debug(f" Found accounts download link for regno={regno}: {href}")
        return href
 
    log.error(f" No accounts download link found for regno={regno}")
    return None
 

def _ocr_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Render each page of a scanned PDF to an image and run Tesseract OCR on it.
    Returns the concatenated text from all pages, or empty string on failure.
    Called only when pdfplumber returns no text (i.e. the PDF is image-based).
    """
    images = convert_from_bytes(pdf_bytes, dpi=OCR_DPI, poppler_path=POPPLER_PATH)
    for img in tqdm(reversed(images), desc="OCR pages", total=len(images)):
        text = pytesseract.image_to_string(img, lang="eng")
        candidate = _find_bank_in_text(text)
        if candidate:
            return candidate
    return ""


def _find_bank_in_text(text: str) -> str:
    """Search extracted PDF text for principal bank references."""
    if not text:
        return ""
 
    # Strategy 1: "Bankers <Name>" or "Bank <Name>" pattern
    banker_re = re.search(
        r"^[Bb]ank(?:ers?)?\s*([A-Z][A-Za-z &]+(?:Bank|Trust|Building Society)?)",
        text
    )
    if banker_re:
        candidate = banker_re.group(1).strip()
        if len(candidate) < 60:
            return candidate
 
    # Strategy 2: known bank name 
    bank_match = BANK_NAME_RE.search(text)
    if bank_match:
        return bank_match.group(1).title()
 
    return ""
 
 
def extract_principal_bank_from_pdf(pdf_url: str, session: requests.Session) -> str:
    """
    Download a charity accounts PDF and extract the principal bank name.
 
    Strategy:
      1. Try pdfplumber text extraction (fast; works on text-layer PDFs).
      2. If that returns empty text, fall back to OCR via pdf2image + pytesseract
         (slower; handles scanned/image-only PDFs).
      3. Search the extracted text for bank name references.
    """
    try:
        resp = session.get(pdf_url, timeout=60, stream=True)
        resp.raise_for_status()
        content_length = int(resp.headers.get("Content-Length", 0))
        
        pdf_bytes = resp.content

        # ---- Stage 1: native text extraction ----
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        if full_text.strip():
            return _find_bank_in_text(full_text)
        
        else:
            # ---- Stage 2: OCR fallback for scanned PDFs ----
            log.error(f" Native text empty for {pdf_url} — attempting OCR fallback")
            return _ocr_pdf_bytes(pdf_bytes)

        
    except Exception as e:
        log.error(f" PDF extraction failed for {pdf_url}: {e}")
        return ""
 


def enrich_bank_for_row(regno: str, session: requests.Session) -> str:
    """Return the principal bank for a single charity, fetching and parsing its accounts PDF."""
    pdf_url = get_accounts_pdf_url(regno, session)
    if not pdf_url:
        return ""
    bank = extract_principal_bank_from_pdf(pdf_url, session)
    return bank
 

if __name__ == "__main__":
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; church-charity-extractor/1.0; +research)"
    })
    
    df = pd.read_csv("uk_churches.csv")

    t0 = time.time()
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Enriching principal_bank"):
        t1 = time.time()
        if (t1 - t0) < PDF_RETRY_DELAY:
            time.sleep(PDF_RETRY_DELAY - (t1 - t0))
        regno = row["registered_number"]
        if row['principal_bank'] and not pd.isna(row['principal_bank']):
            continue
        bank = enrich_bank_for_row(regno, session)
        df.at[idx, "principal_bank"] = bank
        t0 = t1

    df.to_csv("uk_churches.csv", index=False)
    df.loc[df['principal_bank']== "Barclays Bank", 'principal_bank'] = "Barclays"
    df.loc[df['principal_bank']== "National Westminster", 'principal_bank'] = "Natwest"
    df.loc[df['principal_bank']!=""].to_csv("uk_church_with_bank.csv", index=False)