"""品名の読み（ひらがな）を作る部品。品目検索で「でんち」→「電池」と探せるように、また50音の行に分けるのに使う。

  letters(s) … 英字に見えるキリル文字・ギリシャ文字（市のデータにまぎれていることがある）を英字にする
  yomi(name) … ひらがなの読み（漢字・カタカナ・英字をひらがなにする。英字は「えすでぃー」のように1文字ずつ）
必要: pip install pykakasi
"""
import re
import unicodedata

import pykakasi

_KKS = pykakasi.kakasi()
_ABC = {"A": "えー", "B": "びー", "C": "しー", "D": "でぃー", "E": "いー", "F": "えふ", "G": "じー", "H": "えいち", "I": "あい",
        "J": "じぇー", "K": "けー", "L": "える", "M": "えむ", "N": "えぬ", "O": "おー", "P": "ぴー", "Q": "きゅー", "R": "あーる",
        "S": "えす", "T": "てぃー", "U": "ゆー", "V": "ぶい", "W": "だぶりゅー", "X": "えっくす", "Y": "わい", "Z": "ぜっと"}


# 英字とそっくりな文字 → 英字
_LOOK = str.maketrans("АВЕКМНОРСТХаеорсхΑΒΕΖΗΙΚΜΝΟΡΤΥΧ", "ABEKMHOPCTXaeopcxABEZHIKMNOPTYX")


def letters(s):
    return s.translate(_LOOK)


def yomi(name):
    s = unicodedata.normalize("NFKC", letters(name))
    s = re.sub(r"[A-Za-z]", lambda m: _ABC[m.group().upper()], s)
    return "".join(x["hira"] for x in _KKS.convert(s))
