"""Where the collected data lives. Set BANKWELL_DATA to move it (default ~/bankwell-data). Never inside the repo:
it holds accounts PDFs (trustee names) and must not be committed."""
import os
from pathlib import Path

DATA = Path(os.environ.get("BANKWELL_DATA", "~/bankwell-data")).expanduser()
EXTRACT = DATA / "extract"
REPO = Path(__file__).resolve().parent.parent
REGISTER = REPO / "data/raw/publicextract.charity.zip"
PARTB = REPO / "data/raw/publicextract.charity_annual_return_partb.zip"
