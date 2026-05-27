from coe.slot_extractor import _has_anchor, _layer1, extract


# ── station ──────────────────────────────────────────────────────

def test_station_exact():
    assert _layer1("신림역 근처 맛집")["station"] == "신림역"


def test_station_bare():
    # "역" 없이 입력 → 자동 정규화
    assert _layer1("신림 근처 맛집")["station"] == "신림역"


def test_station_long_name():
    assert _layer1("서울대입구역 카페")["station"] == "서울대입구역"


def test_station_none():
    assert _layer1("가성비 좋은 고기집")["station"] is None


# ── category ─────────────────────────────────────────────────────

def test_category_direct():
    assert _layer1("고기집 추천해줘")["category"] == "고기집"


def test_category_synonym():
    assert _layer1("삼겹살집 어디 있어")["category"] == "고기집"


def test_category_none():
    assert _layer1("신림역 근처")["category"] is None


# ── facilities ────────────────────────────────────────────────────

def test_facility_parking():
    assert "주차" in _layer1("주차 되는 식당")["facilities"]


def test_facility_takeout():
    assert "포장" in _layer1("테이크아웃 되나요")["facilities"]


def test_facility_multiple():
    slots = _layer1("주차 예약 가능한 곳")
    assert "주차" in slots["facilities"]
    assert "예약" in slots["facilities"]


def test_facility_none():
    assert _layer1("신림역 고기집")["facilities"] == []


# ── keywords ──────────────────────────────────────────────────────

def test_keyword_gasungbi():
    assert "가격/가성비" in _layer1("가성비 좋은 곳")["keywords"]


def test_keyword_atmosphere():
    assert "분위기/인테리어" in _layer1("분위기 좋은 카페")["keywords"]


def test_keyword_multiple():
    slots = _layer1("분위기 좋고 친절한 식당")
    assert "분위기/인테리어" in slots["keywords"]
    assert "서비스" in slots["keywords"]


def test_keyword_none():
    assert _layer1("신림역 고기집")["keywords"] == []


# ── menu heuristic ────────────────────────────────────────────────

def test_menu_extracted():
    assert _layer1("신림역 냉면 맛집")["menu"] == "냉면"


def test_menu_stopwords_not_extracted():
    # "추천"은 불용어 → menu가 None이어야 함
    assert _layer1("신림역 고기집 추천")["menu"] is None


# ── anchor ────────────────────────────────────────────────────────

def test_has_anchor_station():
    slots = {"station": "신림역", "category": None, "menu": None,
             "keywords": [], "facilities": [], "clarification_needed": None}
    assert _has_anchor(slots)


def test_has_anchor_category():
    slots = {"station": None, "category": "고기집", "menu": None,
             "keywords": [], "facilities": [], "clarification_needed": None}
    assert _has_anchor(slots)


def test_no_anchor():
    slots = {"station": None, "category": None, "menu": None,
             "keywords": [], "facilities": [], "clarification_needed": None}
    assert not _has_anchor(slots)
