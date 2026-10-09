#!/usr/bin/env python3
"""
UK Church Charity Data Extractor
=================================
Extracts data for all registered UK church charities from the Charity Commission
open data, enriches with denomination (via keyword parsing + OpenRouter LLM fallback)
and principal bank (via PDF accounts parsing), and outputs a CSV.
 
Requirements:
    pip install requests pandas pdfplumber tqdm pdf2image pytesseract
    # Also install system dependencies for OCR:
    #   Linux:  sudo apt install tesseract-ocr poppler-utils
    #   macOS:  brew install tesseract poppler
    #   Windows: install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
    #            install poppler from https://github.com/oschwartz10612/poppler-windows/releases
 
Usage:
    python church_charity_extractor.py [--limit N] [--output output.csv] [--skip-pdf] [--skip-denomination-api]
 
Environment variables:
    OPENROUTER_API_KEY  — required for denomination fallback via OpenRouter
                          Get a free key at https://openrouter.ai
                          Free models (no billing needed): mistralai/mistral-7b-instruct:free,
                          google/gemma-3-12b-it:free, meta-llama/llama-3.1-8b-instruct:free
"""

import argparse
import csv
import io
import logging
import os
import re
import sys
import time
import zipfile
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd
import requests
from tqdm import tqdm

from openai import OpenAI
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# Charity Commission open-data bulk download URLs
# Published at: https://register-of-charities.charitycommission.gov.uk/register/full-register-download
# Files are tab-separated .txt files inside zip archives.
CC_BASE_URL = "https://ccewuksprdoneregsadata1.blob.core.windows.net/data/txt"
CC_FILES = {
    # Core charity record: name, regno, status, objects text, contact details (web, postcode)
    "main":    f"{CC_BASE_URL}/publicextract.charity.zip",
    # Annual return part A: financial summary (income, expenditure) 
    "finance_a": f"{CC_BASE_URL}/publicextract.charity_annual_return_parta.zip",
    # Annual return part B: financial details (income, expenditure, funds, assets)
    "finance_b": f"{CC_BASE_URL}/publicextract.charity_annual_return_partb.zip",
    # Annual return history: links financial years to submission dates
    "history": f"{CC_BASE_URL}/publicextract.charity_annual_return_history.zip",
}

# Charity Commission charity detail page (for getting denomination info)
CC_OVERVIEW_PAGE = (
    "https://register-of-charities.charitycommission.gov.uk/"
    "en/charity-search/-/charity-details/{regno}/charity-overview"
    "?_uk_gov_ccew_onereg_charitydetails_web_portlet_CharityDetailsPortlet_organisationNumber={regno}"
) 
# Charity Commission charity accounts page (for locating accounts PDFs)
CC_ACCOUNTS_PAGE = (
    "https://register-of-charities.charitycommission.gov.uk"
    "/en/charity-search/-/charity-details/{regno}/accounts-and-annual-returns"
    "?_uk_gov_ccew_onereg_charitydetails_web_portlet_CharityDetailsPortlet_organisationNumber={regno}"
)

REQUEST_TIMEOUT = 3         # seconds
PDF_RETRY_DELAY = 0.5       # seconds between PDF downloads
MAX_PDF_SIZE_MB = 20        # skip PDFs larger than this
OCR_DPI = 200
POPPLER_PATH = r"C:\Users\stefa\Downloads\Release-26.02.0-0\poppler-26.02.0\Library\bin"
TESSERACT_PATH = r"C:\Users\stefa\AppData\Local\Programs\Tesseract-OCR"
os.environ["PATH"] = os.environ["PATH"] + os.pathsep + TESSERACT_PATH

# OpenRouter API — OpenAI-compatible endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1"
# see https://openrouter.ai/models to choose a specific model 
OPENROUTER_MODEL = "openrouter/free"
 
# Rate limiter: max 10 LLM API requests per second
LLM_MAX_RPS = 1
 
# Maps output column name → list of source column candidates (first match wins)
OUTPUT_COLUMNS = {
    "charity_name":      ["charity_name", "name", "org_name"],
    "registered_number": ["registered_charity_number", "regno", "charity_number"],
    "contact_postcode":  ["charity_contact_postcode", "postcode", "post_code"],
    "contact_web":       ["charity_contact_web", "web", "website", "web_address"],
    "income":            ["total_gross_income", "income", "total_income", "gross_income", "latest_income"],
    "expenditure":       ["total_gross_expenditure", "expenditure", "total_expenditure", "gross_expenditure", "latest_expenditure"],
    "denomination":      ["denomination"],
    "principal_bank":    ["principal_bank"],
    "reserves":          ["reserves"],
    "assets_total": ["assets_total_fixed"],
    "assets_cash":       ["assets_cash"],
    "funds_total":       ["funds_total"]
}
OUTPUT_FIELD_NAMES = list(OUTPUT_COLUMNS.keys())

 
# ---------------------------------------------------------------------------
# Rate limiter (token-bucket style using a sliding window)
# ---------------------------------------------------------------------------
 
class RateLimiter:
    """
    Sliding-window rate limiter. Ensures no more than `max_calls` requests
    are made within any `period` second window.
    """
    def __init__(self, max_calls: int, period: float = 1.0):
        self.max_calls = max_calls
        self.period = period
        self._timestamps: deque = deque()
 
    def wait(self):
        """Block until a request slot is available."""
        now = time.monotonic()
        # Evict timestamps outside the current window
        while self._timestamps and self._timestamps[0] <= now - self.period:
            self._timestamps.popleft()
 
        if len(self._timestamps) >= self.max_calls:
            # Sleep until the oldest timestamp leaves the window
            sleep_for = self.period - (now - self._timestamps[0])
            if sleep_for > 0:
                time.sleep(sleep_for)
            # Re-prune after sleeping
            now = time.monotonic()
            while self._timestamps and self._timestamps[0] <= now - self.period:
                self._timestamps.popleft()
 
        self._timestamps.append(time.monotonic())
 
 
_llm_rate_limiter = RateLimiter(max_calls=LLM_MAX_RPS, period=1.0)
 

# ---------------------------------------------------------------------------
# Step 1: Download & load Charity Commission bulk data
# ---------------------------------------------------------------------------

def download_zip_tsv(url: str, label: str, prv_download_path:str=""
    ) -> pd.DataFrame:
    """
    Download a zipped tab-separated file from the Charity Commission open data portal.
    CC bulk files are .txt (TSV) inside zip archives.
    """
    if Path(prv_download_path).exists():
        with open(prv_download_path, "r", encoding="utf-8") as f:
            df = pd.read_csv(f, sep="\t", encoding="utf-8", low_memory=False, on_bad_lines="skip")
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        log.info(f"Loaded {label} from existing file.")
        return df
    else:
        log.info(f"Downloading {label} ...")
        log.info(f"  URL: {url}")
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        name = zf.namelist()[0]
        log.info(f"  Reading '{name}' from zip ...")
        with zf.open(name) as f:
            df = pd.read_csv(
                f,
                sep="\t",
                encoding="utf-8",
                low_memory=False,
                quoting=csv.QUOTE_NONE,
                on_bad_lines="skip",
            )
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        log.info(f"  {len(df):,} rows loaded. Columns: {list(df.columns)}")
    return df



def _find_col(df: pd.DataFrame, candidates: list, default:str="") -> str:
    """Return the first candidate column name that exists in df."""
    for c in candidates:
        if c in df.columns:
            return c
    # Try partial match
    for c in candidates:
        matches = [col for col in df.columns if c in col]
        if matches:
            return matches[0]
    if default:
        return default
    raise ValueError(f"None of {candidates} found in columns: {list(df.columns)}")


def load_charity_commission_data() -> tuple:
    """
    Download and join the Charity Commission bulk datasets into a single
    DataFrame of active registered charities.

    The main charity file contains:
      - registered_charity_number, charity_name, charity_registration_status
      - charity_contact_web, charity_contact_phone, charity_contact_email
      - charity_contact_address*, charity_contact_postcode
      - latest_income, latest_expenditure
      - charity_activities (objects text — used for denomination)
    So a single file gives us most fields; we only need annual_return_parta
    for verified per-year income/expenditure figures.
    """
    main_df    = download_zip_tsv(CC_FILES["main"],    "main charity register",
        r"C:\Users\stefa\Downloads\publicextract.charity\publicextract.charity.txt")
    finance_df = download_zip_tsv(CC_FILES["finance_b"], "annual return part B (financials)",
        r"C:\Users\stefa\Downloads\publicextract.charity_annual_return_partb\publicextract.charity_annual_return_partb.txt")

    # ---- Filter main register: registered (active) charities only ----
    # Status column is 'charity_registration_status'; value 'Registered'
    status_col = 'charity_registration_status'
    if status_col in main_df.columns:
        main_df = main_df[
            main_df[status_col].astype(str).str.lower().str.startswith("reg")
        ]
        log.info(f"After filtering to registered charities: {len(main_df):,} rows")
    else:
        log.warning("Could not find registration status column — no status filter applied")

    reg_num_col = _find_col(
        main_df, 
        OUTPUT_COLUMNS["registered_number"], 
        main_df.columns[2]  # third column as last resort
    )  


    income_col = _find_col(
        finance_df,
        OUTPUT_COLUMNS["income"] + [c for c in finance_df.columns if "income" in c and "total" in c],
        ""
    )
    expenditure_col = _find_col(
        finance_df,
        OUTPUT_COLUMNS["expenditure"] + [c for c in finance_df.columns if "expenditure" in c and "total" in c],
        ""
    )
    other_finance_cols = [_find_col(finance_df, [col], "") for col in [
        "reserves",
        "assets_total_fixed",
        "assets_cash",
        "funds_total"
    ]]

    if income_col == "" and expenditure_col == "":
        df = main_df  # no financials available
        log.warning("Could not find income/expenditure columns in finance data — financials will be missing")
    else:
        finance_cols = [reg_num_col]
        if income_col:
            finance_cols.append(income_col)
        if expenditure_col:
            finance_cols.append(expenditure_col)
        finance_cols.extend([col for col in other_finance_cols if col != ""])
        # ---- Merge: main + financials ----
        df = main_df.merge(
            finance_df[finance_cols],
            left_on=reg_num_col, right_on=reg_num_col, how="left",
            suffixes=("", "_fin")
        ).drop_duplicates(subset=[reg_num_col])

    log.info(f"Merged dataset: {len(df):,} charities. Columns: {list(df.columns)}")
    return df, reg_num_col, income_col, expenditure_col


# ---------------------------------------------------------------------------
# Step 2: Filter to churches
# ---------------------------------------------------------------------------

CHURCH_KEYWORDS = [
    r"\bchurch\b", r"\bchurches\b", r"\bparish\b", r"\bcongregation\b",
    r"\bchapel\b", r"\bcathedral\b", r"\bminster\b", r"\babbey\b",
    r"\bdiocese\b", r"\bchristian\b", r"\bgospel\b", r"\bworship\b",
    r"\bfellowship\b", r"\bassembly of god\b", r"\bpentecostal\b",
    r"\bbaptist\b", r"\bmethodist\b", r"\bpresbyterian\b",
    r"\banglican\b", r"\bcatholic\b", r"\bquaker\b", r"\bevangel",
]
CHURCH_PATTERN = re.compile("|".join(CHURCH_KEYWORDS), re.IGNORECASE)


def filter_churches(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter the dataset to charities that are likely churches.
    Searches charity name and objects/activities text.
    The CC main file includes 'charity_activities' which contains the objects text.
    """
    # The CC file uses 'charity_name'; fall back to other names if schema changes
    name_col = next(
        (c for c in ["charity_name", "name", "org_name"] if c in df.columns),
        df.columns[1]  # second column as last resort
    )
    # Text columns to search: activities, objects, classification, description
    text_cols = [
        c for c in df.columns
        if any(k in c for k in ["activit", "object", "classif", "purpose", "description"])
    ]
    log.info(f"Filtering churches using name col='{name_col}', text cols={text_cols}")

    mask = df[name_col].astype(str).str.contains(CHURCH_PATTERN, na=False)
    for col in text_cols:
        mask |= df[col].astype(str).str.contains(CHURCH_PATTERN, na=False)

    churches = df[mask].copy()
    log.info(f"Identified {len(churches):,} churches from {len(df):,} registered charities")
    return churches


# ---------------------------------------------------------------------------
# Step 3: Denomination — keyword parsing + Claude API fallback
# ---------------------------------------------------------------------------

DENOMINATION_PATTERNS = [
    # (regex pattern, denomination label)  — ordered most-specific first
    (r"\bRoman Catholic\b|\bCatholic\b",                        "Roman Catholic"),
    (r"\bChurch of England\b|\bAnglican\b|\bCoE\b|\bdiocese\b", "Church of England"),
    (r"\bMethodist\b",                                           "Methodist"),
    (r"\bBaptist\b",                                             "Baptist"),
    (r"\bPentecostal\b|\bAssemblies of God\b|\bElim\b",         "Pentecostal"),
    (r"\bPresbyterian\b",                                        "Presbyterian"),
    (r"\bUnited Reformed\b|\bURC\b",                            "United Reformed Church"),
    (r"\bSalvation Army\b",                                      "Salvation Army"),
    (r"\bQuaker\b|\bFriends\b",                                  "Quaker"),
    (r"\bLutheran\b",                                            "Lutheran"),
    (r"\bEastern Orthodox\b|\bOrthodox\b",                       "Orthodox"),
    (r"\bEvangel",                                               "Evangelical"),
    (r"\bChurch of Scotland\b",                                  "Church of Scotland"),
    (r"\bChurch of Ireland\b",                                   "Church of Ireland"),
    (r"\bChurch of Wales\b",                                     "Church of Wales"),
    (r"\bAdventist\b",                                           "Seventh-day Adventist"),
    (r"\bMoravian\b",                                            "Moravian"),
    (r"\bChurch of Christ\b",                                    "Church of Christ"),
    (r"\bChristian Science\b",                                   "Christian Science"),
    (r"\bJehovah.s Witness\b",                                   "Jehovah's Witnesses"),
    (r"\bLatter.day Saints?\b|\bMormon\b",                       "Latter-day Saints"),
    (r"\bNewfrontiers\b|\bIllumine\b|\bVineyard\b",              "Charismatic/New Church"),
    (r"\bCommunity Church\b|\bNew Church\b",                     "Community/New Church"),
    (r"\bInterdenominat\b|\bnon.denominat\b|\bAll Saints\b|\bAll Nations\b",
                                                                  "Non-denominational"),
]
DENOM_RE = [(re.compile(pat, re.IGNORECASE), label) for pat, label in DENOMINATION_PATTERNS]
ACTIVITIES_RE = re.compile(r'Activities.*?<p>(.*?)</p>', re.DOTALL)  # to find the activities/objects text column

def classify_denomination_keywords(text: str) -> str | None:
    """Return denomination from keyword matching, or None if ambiguous."""
    for pattern, label in DENOM_RE:
        if pattern.search(text):
            return label
    return None


def classify_denomination_llm(name: str, description:str, client: OpenAI) -> str:
    """
    Use OpenRouter (free LLM) to classify the denomination for ambiguous cases.
    Respects the global rate limiter before making each request.
    Returns a short denomination string, or 'Unknown'.
    """
    
    prompt = (
        "You are classifying UK charities by Christian denomination.\n\n"
        f"Charity name: {name}\n"
        f"Objects/description text: {description}\n\n"
        "Based only on the above, what Christian denomination does this charity belong to?\n"
        "Reply with ONLY the denomination name (e.g. 'Baptist', 'Church of England', "
        "'Roman Catholic', 'Non-denominational', 'Unknown'). "
        "Use 'Unknown' if you cannot determine it. No explanation, just the denomination name."
    )
 
    _llm_rate_limiter.wait()  # enforce ≤10 req/s
 
    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content.strip()
        # Sanitise: take only the first line and cap length
        answer = answer.splitlines()[0].strip()[:60]
        return answer if answer else "Unknown"
    except Exception as e:
        log.warning(f"OpenRouter API call failed for '{name}': {e}")
        return "Unknown"
 


def enrich_denomination_for_row(row: pd.Series, regno: str, name_col: str, text_cols: list, session: requests.Session, client: OpenAI | None) -> str:
    """Return the denomination for a single charity row."""
    combined = " ".join(str(row.get(c, "")) for c in [name_col] + text_cols)
    result = classify_denomination_keywords(combined)
    if result is not None:
        return result
    if client:
        name    = str(row.get(name_col, ""))
        try:
            # obtain more details about the church in order for the LLM to have a description to classify from. 
            resp = session.get(CC_OVERVIEW_PAGE.format(regno=regno), timeout=REQUEST_TIMEOUT)

            activities_match = ACTIVITIES_RE.search(resp.text) 
            description = activities_match.group(1).strip() if activities_match else resp.text or ""
            return classify_denomination_llm(name, description, client)
        except Exception as e:
            log.warning(f"Error occurred while fetching overview page for regno={regno}: {e}")
            
    return "Unknown"


# ---------------------------------------------------------------------------
# Step 4: Principal bank — fetch PDF, extract text, search for bank name
# ---------------------------------------------------------------------------
 
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
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        log.debug(f" Could not fetch accounts page for regno={regno}: {e}")
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
 
    log.debug(f"  No accounts download link found for regno={regno}")
    return None
  
 
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
        if content_length > MAX_PDF_SIZE_MB * 1024 * 1024:
            log.debug(f"Skipping oversized PDF ({content_length/1e6:.1f} MB): {pdf_url}")
            return ""
        
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
        log.debug(f"PDF extraction failed for {pdf_url}: {e}")
        return ""

 
 
# def add_principal_bank_column(df: pd.DataFrame, reg_num_col: str) -> pd.DataFrame:
#     """Add a 'principal_bank' column by downloading and parsing each charity's accounts PDF."""
#     session = requests.Session()
#     session.headers.update({
#         "User-Agent": "Mozilla/5.0 (compatible; church-charity-extractor/1.0; +research)"
#     })
 
#     banks = []
#     log.info("Fetching principal bank from PDF accounts (this will take several hours for the full set) ...")
#     for _, row in tqdm(df.iterrows(), total=len(df), desc="PDF bank extraction"):
#         t0 = time.time()
#         regno   = str(row[reg_num_col])
#         pdf_url = CC_ACCOUNTS_URL.format(regno=regno)
#         bank    = extract_principal_bank_from_pdf(pdf_url, session)
#         banks.append(bank)
#         elapsed = time.time() - t0
#         if elapsed < PDF_RETRY_DELAY:
#             time.sleep(PDF_RETRY_DELAY - elapsed)
 
#     df = df.copy()
#     df["principal_bank"] = banks
#     found = sum(1 for b in banks if b)
#     log.info(f"Principal bank found for {found:,} / {len(banks):,} charities")
#     return df
 
 
def enrich_bank_for_row(regno: str, session: requests.Session) -> str:
    """Return the principal bank for a single charity, fetching and parsing its accounts PDF."""
    pdf_url = get_accounts_pdf_url(regno, session)
    if not pdf_url:
        return ""
    bank = extract_principal_bank_from_pdf(pdf_url, session)
    return bank
 
# ---------------------------------------------------------------------------
# Step 5: Incremental CSV — row-by-row enrichment with resume support
# ---------------------------------------------------------------------------
 
 
 
def _resolve_row_values(row: pd.Series, denomination: str, bank: str) -> dict:
    """Build the output dict for one row, resolving source column name variants."""
    out = {}
    for field, candidates in OUTPUT_COLUMNS.items():
        if field == "denomination":
            out[field] = denomination
        elif field == "principal_bank":
            out[field] = bank
        else:
            for c in candidates:
                if c in row.index and pd.notna(row[c]):
                    out[field] = row[c]
                    break
            else:
                out[field] = ""
    return out
 
 
def enrich_and_write(
    churches: pd.DataFrame,
    reg_num_col: str,
    output_path: str,
    api_key: str | None,
    skip_pdf: bool,
) -> None:
    """
    Core enrichment loop: for each church, determine denomination and principal bank,
    then immediately append the completed row to the output CSV.
 
    Resume behaviour: if the output CSV already exists (from a previous interrupted
    run), any charity number already present is skipped — processing continues from
    where it left off.
    """
    # ---- Identify source columns for denomination text ----
    name_col = next(
        (c for c in ["charity_name", "name", "org_name"] if c in churches.columns),
        churches.columns[1]
    )
    text_cols = [
        c for c in churches.columns
        if any(k in c for k in ["activit", "object", "classif", "purpose", "description"])
    ]
 
    # ---- HTTP session reused across all PDF requests ----
    http_session = requests.Session()
    http_session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; church-charity-extractor/1.0; +research)"
    })

    resp = http_session.get("https://register-of-charities.charitycommission.gov.uk/en/charity-search/-/charity-details/216443/accounts-and-annual-returns?_uk_gov_ccew_onereg_charitydetails_web_portlet_CharityDetailsPortlet_organisationNumber=216443")

    # ---- Initialize OpenAI client ----
    if api_key:
        client = OpenAI(api_key=api_key, base_url=OPENROUTER_API_URL)
 
    # ---- Resume: load already-processed charity numbers ----
    already_done: set = set()
    output_file = Path(output_path)
    if output_file.exists():
        try:
            existing = pd.read_csv(output_file, usecols=["registered_number"], dtype=str)
            already_done = set(existing["registered_number"].dropna().astype(str))
            log.info(f"Resuming: {len(already_done):,} rows already in {output_path}, skipping them")
        except Exception as e:
            log.warning(f"Could not read existing output for resume ({e}) — starting fresh")
 
    # ---- Open CSV for appending (write header only if file is new) ----
    write_header = not output_file.exists() or len(already_done) == 0
    csv_file = open(output_path, "a", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_FIELD_NAMES)
    if write_header:
        writer.writeheader()
 
    # ---- Main loop ----
    total      = len(churches)
    skipped    = 0
    processed  = 0
    bank_found = 0
    t0 = time.time()
    
    
    try:
        for _, row in tqdm(churches.iterrows(), total=total, desc="Enriching churches"):
            regno = str(row.get(reg_num_col, ""))
 
            if regno in already_done:
                skipped += 1
                continue
 
            # Denomination
            if api_key:
                denomination = enrich_denomination_for_row(row, regno, name_col, text_cols, http_session, client)
            else:
                denomination = "Unknown"  
 
            # Principal bank
            if skip_pdf:
                bank = ""
            else:
                t1 = time.time()
                elapsed = t1 - t0
                if elapsed < PDF_RETRY_DELAY:
                    time.sleep(PDF_RETRY_DELAY - elapsed)
                
                t0 = t1
                bank = enrich_bank_for_row(regno, http_session)
                if bank:
                    bank_found += 1
 
            # Write this row immediately
            writer.writerow(_resolve_row_values(row, denomination, bank))
            csv_file.flush()   # ensure it hits disk even if we crash next iteration
 
            processed += 1
 
    except Exception:
        # Re-raise after flushing so the caller sees the error, but the CSV is intact
        csv_file.flush()
        log.error(
            f"Unhandled exception after processing {processed:,} rows "
            f"({skipped:,} skipped as already done). "
            f"Output saved to {output_path} — re-run to resume."
        )
        raise
    finally:
        csv_file.close()
 
    log.info(
        f"✓ Done. {processed:,} rows written ({skipped:,} skipped), "
        f"principal bank found for {bank_found:,} churches. \nOutput: {output_path}"
    )
 
 
# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------
 
def main():
    parser = argparse.ArgumentParser(description="Extract UK church charity data to CSV")
    parser.add_argument("--limit",    type=int,  default=None,
                        help="Process only the first N churches (for testing)")
    parser.add_argument("--output",   type=str,  default="uk_churches.csv",
                        help="Output CSV filename (default: uk_churches.csv)")
    parser.add_argument("--skip-pdf", action="store_true",
                        help="Skip PDF download/parsing (principal_bank will be empty)")
    parser.add_argument("--skip-denomination-api", action="store_true",
                        help="Skip LLM fallback for denomination; use keyword matching only")
    args = parser.parse_args()
 
    # ---- Set up OpenRouter API key ----
    load_dotenv()  
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key and not args.skip_denomination_api:
        log.warning(
            "OPENROUTER_API_KEY not set. LLM fallback for denomination will be skipped.\n"
            "  Get a free key at https://openrouter.ai and set it with:\n"
            "  export OPENROUTER_API_KEY=sk-or-...\n"
            "  Or use --skip-denomination-api to suppress this warning."
        )
 
    
    # ---- Pipeline ----
    log.info("=== UK Church Charity Extractor ===")
    log.info(f"LLM model: {OPENROUTER_MODEL} | Rate limit: {LLM_MAX_RPS} req/s")
    
    df, reg_num_col, income_col, expenditure_col = load_charity_commission_data()
    log.info(f"Income column: {income_col} | Expenditure column: {expenditure_col}")
 
    churches = filter_churches(df)
 
    if args.limit:
        log.info(f"Limiting to first {args.limit} churches for testing")
        churches = churches.head(args.limit)
 
    enrich_and_write(
        churches,
        reg_num_col=reg_num_col,
        output_path=args.output,
        api_key=api_key if not args.skip_denomination_api else None,
        skip_pdf=args.skip_pdf,
    )
 
    log.info("=== Done ===")
 
 
if __name__ == "__main__":
    main()
 