import pandas as pd


df = pd.read_csv("filtered data.csv", encoding="cp1252")
df = df[~df["charity_name"].isin(["TEARFUND", "FARMLAND RESERVE UK LIMITED"])]
df = df[~df["charity_name"].str.contains("YMCA")]

cb = pd.read_csv("church_banks_extended.csv", encoding="cp1252")
print(len(cb) / pd.unique(cb.charity_number).shape[0])
print(len(df) / pd.unique(df.registered_number).shape[0])

# remove "osm:way/" prefix from cb charity number column
cb["charity_number"] = cb["charity_number"].str.replace("osm:way/", "")
cb["charity_number"] = cb["charity_number"].str.replace("osm:node/", "")
cb["charity_number"] = cb["charity_number"].str.replace("osm:relation/", "")
# convert to int type
cb["charity_number"] = cb["charity_number"].astype(df.dtypes["registered_number"])


# add the information from cb to df based on the registered_number and charity_number columns, but we only want the bank and rating column from cb
# the principal_bank from df and bank column from cb need merging, choosing from whichever is not NaN, or taking from cb.bank if both exist
merged_df = pd.merge(df, cb[["charity_number", "bank", "rating"]], how="left", left_on="registered_number", right_on="charity_number")
merged_df["principal_bank"] = merged_df["principal_bank"].fillna(merged_df["bank"])
merged_df.drop(columns=["bank", "charity_number"], inplace=True)

# show me the number of rows in merged_df that have a NaN value in the bank column
print("banks filled: ", merged_df["principal_bank"].notna().sum(), "/", len(merged_df))
print("banks filled: ", merged_df["principal_bank"].notna().sum() / len(merged_df) * 100, "%")

og = pd.read_csv("C:\\Users\\stefa\\Downloads\\publicextract.charity\\publicextract.charity.txt", sep="\t", encoding="utf-8", on_bad_lines="skip")

# add the charity_contact_postcode column from og to merged_df based on the charity name column, but we need to make sure that the charity name columns are in the same case and stripped of whitespace
merged_df["lowercase"] = merged_df["lowercase"].str.lower().str.strip()
og["lowercase"] = og["charity_name"].str.lower().str.strip()
mdf2 = pd.merge(merged_df, og[["lowercase", "charity_contact_postcode"]], how="left", left_on="lowercase", right_on="lowercase")

print("banks filled: ", mdf2["principal_bank"].notna().sum(), "/", len(merged_df))


# df has filtered out the schools, but df2 has more bank info, so we merge them.
df2 = pd.read_csv("results/bankwell_churches_matched.csv")
df2 = df2[~df2["charity_name"].isin(["TEARFUND", "FARMLAND RESERVE UK LIMITED"])]
df2 = df2[~df2["charity_name"].str.contains("YMCA")]
df2["bank"] = df2["principal_bank_existing"].fillna(df2["bank_named_on_page"]).fillna(df2["bank_from_sort_code"])
mdf2 = pd.merge(mdf2, df2[["charity_number", "bank"]], how="left", left_on="registered_number", right_on="charity_number")
mdf2["principal_bank"] = mdf2["principal_bank"].fillna(mdf2["bank"])
mdf2.drop(columns=["bank", "charity_number"], inplace=True)

print("banks filled: ", mdf2["principal_bank"].notna().sum(), "/", len(mdf2))

# clean the banks names 
## take only first bank in list
mdf2["principal_bank"] = mdf2["principal_bank"].str.split(";").str[0]
## same case, use first letter capitalized
mdf2["principal_bank"] = mdf2["principal_bank"].str.title().str.strip()
## fix different spellings
mdf2["principal_bank"] = mdf2["principal_bank"].replace({
    "Barclays Bank": "Barclays",
    "National Westminster": "Natwest",
    "Nat West": "Natwest"
})


# what to do with multiple banks?


asset = pd.read_csv("results/pdf_extract_final.csv").rename(columns={"assets_cash": "cash"})
print("rows with assets_cash information: ", asset["cash"].notna().sum() )

mdf3 = mdf2.merge(asset[["registered_number", "cash"]], how="left", left_on="registered_number", right_on="registered_number")
mdf3["assets_cash"] = mdf3["assets_cash"].fillna(mdf3["cash"])

res = mdf3[mdf3["principal_bank"].notna()]
resnna = res[res["assets_cash"].notna()]

rank = {
    "Barclays": 1,
    "Hsbc": 1,
    "Natwest": 1,
    "Standard Chartered": 1,
    "Santander": 1,
    "Tsb": 1,
    "Bank Of Scotland": 3,
    "Halifax": 3,
    "Lloyds": 3,
    "Tide": 4,
    "Caf Bank": 5,
    "Co-Operative Bank": 5,
    "Charity Bank": 5,
    "Clydesdale": 5,
    "Handelsbanken": 5,
    "Nationwide": 5,
    "Metro Bank": 5,
    "Unity Trust": 5,
    "Triodos": 5,
    "Virgin Money": 5,
    "Yorkshire Bank": 5,    
}

resnna["rating"] = resnna["principal_bank"].map(rank).fillna(0)

# remove YMCA and TEARFUND from the list of banks in resnna
resnna = resnna[~resnna["charity_name"].isin(["TEARFUND", "FARMLAND RESERVE UK LIMITED"])]
resnna = resnna[~resnna["charity_name"].str.contains("YMCA")]


print(f"""
Found {len(mdf3)} churches, 
of which {mdf3.principal_bank.notna().sum()} have been assigned a bank, 
and {mdf3.assets_cash.notna().sum()} have asset cash information, 
and {len(resnna)} have both bank and cash information.
churches with ethical banks: {(resnna.rating > 3).sum()} = {((resnna.rating > 3).sum() / len(resnna) * 100):.2f}%
cash in ethical banks: £{resnna.assets_cash[resnna.rating > 3].sum()/1e6:.2f} million
churches with unethical banks: {(resnna.rating <= 3).sum()} = {((resnna.rating <= 3).sum() / len(resnna) * 100):.2f}%
cash in unethical banks: £{resnna.assets_cash[resnna.rating <= 3].sum()/1e6:.2f} million
""")

