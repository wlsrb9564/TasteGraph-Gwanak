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
