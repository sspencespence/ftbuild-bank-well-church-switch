from church_check import classify

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
