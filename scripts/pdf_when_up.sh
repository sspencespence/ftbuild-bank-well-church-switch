#!/usr/bin/env bash
# Run fetch_accounts.py only while the Charity Commission PDF store is answering.
# Every 10 minutes, probe 3 different churches (fresh link from each accounts page). If ANY returns
# a real PDF, run the resumable fetcher over all remaining churches.
cd "$(dirname "$0")/.." || exit 1
UA="Mozilla/5.0 (compatible; bankwell-church-research/1.0; FaithTech BUILD 2026)"
PAGE='https://register-of-charities.charitycommission.gov.uk/en/charity-search/-/charity-details/%s/accounts-and-annual-returns'
PROBE_ORGS="5014742 5006556 5005394"   # St Paul Woking, St Margaret Lowestoft, Cheam (parish PCCs)

store_up() {
  for org in $PROBE_ORGS; do
    link=$(curl -s -A "$UA" -m 30 "$(printf "$PAGE" "$org")" | grep -oE 'href="[^"]*accounts-resource[^"]*"' | head -1 | sed 's/^href="//;s/"$//;s/&amp;/\&/g')
    [ -z "$link" ] && { echo "  probe org $org: links hidden"; continue; }
    ctype=$(curl -s -A "$UA" -o /dev/null -m 60 -w "%{content_type}" "$link")
    echo "  probe org $org: ${ctype:-timeout}"
    [[ "$ctype" == application/pdf* ]] && return 0
  done
  return 1
}

while true; do
  echo "$(date '+%F %T') probing PDF store"
  if store_up; then
    echo "$(date '+%F %T') PDF store UP - running fetcher"
    python3 scripts/fetch_accounts.py --register data/raw/publicextract.charity.zip --out ~/bankwell-data --workers 3
    echo "$(date '+%F %T') fetcher exited ($?)"
  else
    echo "$(date '+%F %T') PDF store down - retry in 10 min"
  fi
  sleep 600
done
