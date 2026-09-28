"""욕설/비속어 검열.

화면에서 한 번 거르지만, 그건 API 를 직접 두드리면 그냥 지나간다.
그래서 진짜 검열은 여기, 서버에서 한다.

단어만 비교하면 tlqkf(영타로 친 시발) 같은 건 그냥 통과한다.
그래서 비교하기 전에 글을 여러 방식으로 "펴서" 각각 확인한다.
게임 회사 필터들이 쓰는 방식과 같다.
"""
import re
import unicodedata


# ── 막을 말 (400 으로 거절) ────────────────────────────────
BLOCKED = [
    # 시발 계열
    "시발", "씨발", "씨팔", "시팔", "씨빨", "시바루", "씹할", "씨발놈", "씨발년",
    "개시발", "존시발", "시발새끼", "썅", "썅년", "썅놈",
    # 병신 계열
    "병신", "빙신", "병싄", "등신새끼", "장애인새끼",
    # 좆 계열
    "좆", "좇", "존나", "졸라", "좆같", "좆만", "개좆",
    # 새끼 계열
    "개새끼", "개색기", "개색끼", "새끼", "쌔끼", "썌끼", "잡새끼", "개자식",
    # 지랄 계열
    "지랄", "짓랄", "지럴", "미친놈", "미친년", "미친새끼",
    # 패드립
    "니미", "니애미", "니미럴", "애미", "애비", "엄창", "느금마", "느검마",
    "니애비", "패드립", "호로새끼", "후레자식",
    # 성적 표현
    "보지", "자지", "섹스", "야동", "포르노", "강간", "성기", "자위",
    # 영어
    "fuck", "fuk", "fck", "shit", "bitch", "asshole", "bastard",
    "dick", "cunt", "pussy", "whore", "slut", "nigger", "nigga",
    "motherfucker", "retard", "rape",
]

# ── 가릴 말 (** 로 덮고 통과) ──────────────────────────────
MASKED = [
    "바보", "멍청이", "찌질이", "루저", "돌대가리", "머저리", "등신",
    "빡대가리", "골빈", "찐따", "핵noob", "노답", "찌질",
    "damn", "idiot", "stupid", "moron", "loser", "noob", "trash",
]

# ── 자음만 쓴 욕 ───────────────────────────────────────────
BLOCKED_JAMO = [
    "ㅅㅂ", "ㅆㅂ", "ㅅㅃ", "ㅄ", "ㅂㅅ", "ㅈㄹ", "ㄱㅅㄲ", "ㅅㄲ",
    "ㅁㅊ", "ㅆㄹㄱ", "ㄴㄱㅁ", "ㅈㄴ", "ㅆㄱ",
]

# ── 손가락 욕 (모양으로 하는 것) ───────────────────────────
# ㅗ 는 자음 목록에도 있지만, 凸 이나 🖕 는 글자가 아니라 따로 본다
# ㅗ 는 영타 변환에서 s, h 가 ㅗ 로 바뀌어 오탐이 나므로
# 반드시 원문에서만 확인한다 (shit 의 s 가 ㅗ 로 읽히는 것 방지)
GESTURES = ["ㅗ", "凸", "🖕", "🖕🏻", "🖕🏼", "🖕🏽", "🖕🏾", "🖕🏿"]


# ── 펴기(normalize) 재료 ───────────────────────────────────

# 글자 사이 공백/특수문자/숫자를 지운다
_FILLER = re.compile(r"[\s\W\d_]+", re.UNICODE)

# 숫자·기호로 흉내 낸 글자를 되돌린다 (leetspeak)
LEET = {
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
    "7": "t", "8": "b", "9": "g", "@": "a", "$": "s",
    "!": "i", "|": "i", "+": "t", "(": "c",
}

# 영문 자판으로 한글을 친 것을 되돌린다 (tlqkf -> 시발)
# 두벌식 자판 배열 그대로다
_QWERTY_TO_JAMO = {
    "q": "ㅂ", "w": "ㅈ", "e": "ㄷ", "r": "ㄱ", "t": "ㅅ",
    "y": "ㅛ", "u": "ㅕ", "i": "ㅑ", "o": "ㅐ", "p": "ㅔ",
    "a": "ㅁ", "s": "ㄴ", "d": "ㅇ", "f": "ㄹ", "g": "ㅎ",
    "h": "ㅗ", "j": "ㅓ", "k": "ㅏ", "l": "ㅣ",
    "z": "ㅋ", "x": "ㅌ", "c": "ㅊ", "v": "ㅍ",
    "b": "ㅠ", "n": "ㅜ", "m": "ㅡ",
    "Q": "ㅃ", "W": "ㅉ", "E": "ㄸ", "R": "ㄲ", "T": "ㅆ",
    "O": "ㅒ", "P": "ㅖ",
}

# 한글을 합치는 데 쓰는 표 (초성/중성/종성)
_CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
_JUNG = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")
_JONG = list("_ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")

# 겹모음: ㅗ + ㅏ = ㅘ 처럼 두 모음이 하나로 합쳐지는 경우
_COMBO_JUNG = {
    ("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ",
    ("ㅜ", "ㅓ"): "ㅝ", ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ",
    ("ㅡ", "ㅣ"): "ㅢ",
}


def _compose_hangul(jamos: str) -> str:
    """낱자를 모아 글자로 만든다. tlqkf -> ㅅㅣㅂㅏㄹ -> 시발"""
    out = []
    i = 0
    n = len(jamos)

    while i < n:
        ch = jamos[i]

        # 초성이 될 수 있나?
        if ch in _CHO and i + 1 < n and jamos[i + 1] in _JUNG:
            cho = ch
            jung = jamos[i + 1]
            i += 2

            # 겹모음인지 확인
            if i < n and (jung, jamos[i]) in _COMBO_JUNG:
                jung = _COMBO_JUNG[(jung, jamos[i])]
                i += 1

            # 받침이 붙나? 단, 다음 글자의 초성이면 넘긴다
            jong = "_"
            if i < n and jamos[i] in _JONG:
                is_next_cho = (i + 1 < n and jamos[i] in _CHO and jamos[i + 1] in _JUNG)
                if not is_next_cho:
                    jong = jamos[i]
                    i += 1

            code = 0xAC00 + (_CHO.index(cho) * 21 + _JUNG.index(jung)) * 28 + _JONG.index(jong)
            out.append(chr(code))
        else:
            out.append(ch)
            i += 1

    return "".join(out)


def _to_hangul(text: str) -> str:
    """영타로 친 한글을 되돌린다. 한글이 아닌 글자는 그대로 둔다."""
    jamos = "".join(_QWERTY_TO_JAMO.get(c, c) for c in text)
    return _compose_hangul(jamos)


def _strip_repeats(text: str) -> str:
    """시이이이발 처럼 늘려 쓴 걸 시이발 정도로 줄인다(2개까지 남김)."""
    return re.sub(r"(.)\1{2,}", r"\1\1", text)


def _squash_repeats(text: str) -> str:
    """반복을 아예 1개로 줄인다. 시이이이발 -> 시발"""
    return re.sub(r"(.)\1+", r"\1", text)


# 시이이이발 처럼 사이에 모음을 늘려 끼워 넣는 걸 막는다.
# 3번 이상 반복된 모음 덩어리는 통째로 지워 본다
_PADDING = re.compile(r"([ㅏ-ㅣ아야어여오요우유으이])\1{2,}")


def _drop_padding(text: str) -> str:
    """늘려 끼운 모음 덩어리를 지운다. 시이이이발 -> 시발"""
    return _PADDING.sub("", text)


def _decompose(text: str) -> str:
    """글자를 낱자로 푼다. 시발 -> ㅅㅣㅂㅏㄹ

    시바아아알 처럼 글자 속 모음을 늘린 걸 잡으려면
    글자 단위가 아니라 낱자 단위로 봐야 한다.
    """
    out = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out.append(_CHO[code // 588])
            out.append(_JUNG[(code % 588) // 28])
            jong = code % 28
            if jong:
                out.append(_JONG[jong])
        else:
            out.append(ch)
    return "".join(out)


# 시바아아알 처럼 글자 속 모음을 늘린 것 잡기.
# 낱자로 풀면 ㅅㅣㅂㅏ(ㅇㅏ)(ㅇㅏ)(ㅇㅏ)ㄹ 이 되는데,
# 소리 없는 ㅇ + 앞 모음이 되풀이되는 덩어리는 늘려 쓴 것으로 보고 지운다
_VOWEL_PAD = re.compile(r"(?:ㅇ([ㅏ-ㅣ]))(?:ㅇ\1)+")


def _drop_vowel_pad(jamo: str) -> str:
    """늘려 쓴 'ㅇ+모음' 덩어리를 지운다. ㅅㅣㅂㅏㅇㅏㅇㅏㅇㅏㄹ -> ㅅㅣㅂㅏㄹ"""
    return _VOWEL_PAD.sub("", jamo)


def _flatten(text: str) -> str:
    """공백/기호/숫자를 빼고 소문자로 만든다."""
    flat = unicodedata.normalize("NFKC", text)
    flat = _FILLER.sub("", flat)
    return flat.lower()


def _unleet(text: str) -> str:
    """5|8al 같은 숫자·기호 흉내를 글자로 되돌린다."""
    return "".join(LEET.get(c, c) for c in text)


def _variants(text: str):
    """한 글을 여러 방식으로 펴서 전부 돌려준다.

    이 중 하나라도 욕에 걸리면 욕으로 본다.
    """
    seen = []

    def add(value):
        if value and value not in seen:
            seen.append(value)

    base = _strip_repeats(text)

    # 1. 그냥 편 것
    flat = _flatten(base)
    add(flat)

    # 2. leetspeak 되돌린 것 (숫자를 글자로 보므로 편 다음에 한다)
    lowered = _strip_repeats(unicodedata.normalize("NFKC", text).lower())
    add(_flatten(_unleet(lowered)))

    # 3. 영타 -> 한글로 되돌린 것
    add(_flatten(_to_hangul(lowered)))

    # 4. 기호를 지우지 않고 영타만 되돌린 것 (ㅗㅗ 같은 게 살아남게)
    add(_to_hangul(lowered))

    # 5. 반복을 1개로 줄인 것
    squashed = _squash_repeats(_flatten(text))
    add(squashed)

    # 6. 늘려 끼운 모음을 아예 지운 것 (시이이이발 -> 시발)
    add(_drop_padding(_flatten(text)))
    add(_flatten(_to_hangul(_squash_repeats(unicodedata.normalize("NFKC", text).lower()))))

    return seen


def find_blocked(text: str):
    """막아야 할 말이 있으면 그 목록을, 없으면 빈 목록을 준다."""
    if not text:
        return []

    hits = []
    forms = _variants(text)

    # 손가락 욕은 편 글이 아니라 원문에서 본다 (기호라 지워지므로)
    for sign in GESTURES:
        if sign in text:
            hits.append(sign)

    # 글자 속 모음을 늘린 것(시바아아알)은 낱자로 풀어야 잡힌다.
    # 글과 욕을 똑같이 낱자로 풀어서 맞춰 본다
    jamo_form = _drop_vowel_pad(_squash_repeats(_decompose(_flatten(text))))
    for word in BLOCKED:
        if _squash_repeats(_decompose(_flatten(word))) in jamo_form and word not in hits:
            hits.append(word)

    for form in forms:
        for word in BLOCKED:
            if _flatten(word) in form and word not in hits:
                hits.append(word)

        for jamo in BLOCKED_JAMO:
            # NFKC 가 ㅅ(U+3145) 을 ᄉ(U+1109) 으로 바꿔 놓으므로 목록도 같이 편다
            if _flatten(jamo) in form and jamo not in hits:
                hits.append(jamo)

    return hits


def mask(text: str) -> str:
    """가벼운 비속어를 ** 로 덮는다. 글자 수는 그대로 둔다."""
    if not text:
        return text

    result = text
    for word in MASKED:
        result = re.compile(re.escape(word), re.IGNORECASE).sub("*" * len(word), result)
    return result
