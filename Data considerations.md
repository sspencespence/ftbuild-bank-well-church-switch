# Things that could cause too few records

##  missing keywords in the original search

Currently using
```
CHURCH_KEYWORDS = [
    r"\bchurch\b", r"\bchurches\b", r"\bparish\b", r"\bcongregation\b",
    r"\bchapel\b", r"\bcathedral\b", r"\bminster\b", r"\babbey\b",
    r"\bdiocese\b", r"\bchristian\b", r"\bgospel\b", r"\bworship\b",
    r"\bfellowship\b", r"\bassembly of god\b", r"\bpentecostal\b",
    r"\bbaptist\b", r"\bmethodist\b", r"\bpresbyterian\b",
    r"\banglican\b", r"\bcatholic\b", r"\bquaker\b", r"\bevangel",
]
```
(not just in charity name but also description, etc.)


# Things that could cause too many records

## charities that aren't churches
    - use charity commission data to only include classification_code==108 (Religious Activities)
    - colleges/universities - remove "contact_web" which contain "ac.uk" (case insensitive)

## How to remove?
 - TEARFUND (265464), FARMLAND RESERVE UK LIMITED (274605), YMCA (1133269)

```
(
    pd
    .read_csv("uk_churches_trimmed.csv")
    .query("registered_number in [265464, 274605, 1133269]")
)
```
# Missing attributes

## Assets_cash
Can we make some assumptions based on income/expenditure?

## Bank name
### Fetch sort codes from giving web pages
Initial script written and run
### Need sort code to bank lookup table

# Data of interest

https://docs.google.com/spreadsheets/d/1DaD0K8hT_ejmKs3iCh_XoOIEgLs19Rkz3CHHQ3eOAO0/edit?usp=sharing