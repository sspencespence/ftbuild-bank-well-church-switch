from church_check import classify, name_words, osm_name_match, osm_sites, site_key, tidy_postcode

RELIG = ["Religious Activities"]


def check(name, classes=RELIG, activities="", in_team=True):
    return classify(name, classes, activities, in_team)[0]


def test_pcc_with_diocese_in_name_is_church():
    assert check("THE PAROCHIAL CHURCH COUNCIL OF THE ECCLESIASTICAL PARISH OF HALLOW IN THE DIOCESE OF WORCESTER") == "church"


def test_church_word_beats_weak_non_church_words():
    assert check("HADDON HALL BAPTIST CHURCH") == "church"
    assert check("REDEEMED CHRISTIAN CHURCH OF GOD FRUITFUL LAND TILBURY") == "church"


def test_attached_bodies_are_not_churches():
    assert check("THE FRIENDS OF ST ANDREW'S CHURCH ALFRISTON") == "not_church"
    assert check("DITTON CHURCH PRE-SCHOOL") == "not_church"
    assert check("THE CHURCH HALL HUGHENDEN") == "not_church"
    assert check("ST MICHAEL'S HALL") == "not_church"


def test_other_faiths_are_not_churches():
    assert check("USMANI MOSQUE") == "not_church"
    assert check("NORTHOLT ISLAMIC CENTRE", activities="a place of worship for Muslims") == "not_church"


def test_self_described_church_without_church_name():
    assert check("KICC THE CITY OF REFUGE", activities="We are a Pentecostal church with Sunday services") == "church"


def test_vague_religious_charity_is_unsure():
    assert check("THE PENIEL CENTRE", activities="To advance the Christian faith") == "unsure"


def test_no_religious_signal_is_not_church():
    assert check("WYCOMBE HOMELESS CONNECTION", classes=["Accommodation/housing"]) == "not_church"


def test_ymca_spelled_out():
    assert check("BOURNEMOUTH YOUNG MEN'S CHRISTIAN ASSOCIATION") == "not_church"
    assert check("LINCOLNSHIRE Y.M.C.A. LTD") == "not_church"


def test_osm_matches_domain_but_directories_only_by_path(tmp_path):
    osm = tmp_path / "osm.csv"
    osm.write_text("website\nhttps://www.stmarys.org.uk/\n"
                   "https://www.achurchnearyou.com/church/1/\nhttps://www.achurchnearyou.com/church/2/\n"
                   "https://www.achurchnearyou.com/church/3/\n", encoding="utf-8")
    sites, directories = osm_sites(osm)
    assert site_key("stmarys.org.uk/give", directories) in sites
    assert site_key("https://www.achurchnearyou.com/church/2", directories) in sites
    assert site_key("https://www.achurchnearyou.com/church/9/", directories) not in sites
    assert site_key("https://www.achurchnearyou.com/", directories) == ""


def test_osm_name_match_by_postcode_then_district():
    places = ({"MK403EU": [name_words("Bunyan Meeting Free Church")]},
              {"MK40": [name_words("Bunyan Meeting Free Church")]})
    assert osm_name_match("BUNYAN MEETING", "MK40 3EU", places) == "postcode_name"
    assert osm_name_match("BUNYAN MEETING TRUST", "MK40 1AA", places) == "district_name"
    assert osm_name_match("BUNYAN HALL", "MK40 1AA", places) == ""
    assert osm_name_match("BUNYAN MEETING", "", places) == ""


def test_tidy_postcode():
    assert tidy_postcode("bn34ed") == "BN3 4ED"
    assert tidy_postcode(" EC4V 2AF ") == "EC4V 2AF"
    assert tidy_postcode("") == "" and tidy_postcode("N1") == "" and tidy_postcode("LEICESTER") == ""
