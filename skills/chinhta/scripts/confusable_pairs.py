# -*- coding: utf-8 -*-
"""
Database cặp từ dễ nhầm lẫn và collocation cho kiểm tra chính tả tiếng Việt.
"""

HOI_NGA_MAP = {
    "ả": "ã", "ã": "ả", "ẩ": "ẫ", "ẫ": "ẩ", "ẳ": "ẵ", "ẵ": "ẳ",
    "ẻ": "ẽ", "ẽ": "ẻ", "ể": "ễ", "ễ": "ể", "ỉ": "ĩ", "ĩ": "ỉ",
    "ỏ": "õ", "õ": "ỏ", "ổ": "ỗ", "ỗ": "ổ", "ở": "ỡ", "ỡ": "ở",
    "ủ": "ũ", "ũ": "ủ", "ử": "ữ", "ữ": "ử", "ỷ": "ỹ", "ỹ": "ỷ"
}

# Các từ sai ngữ cảnh nguy hiểm (Đã thêm rút cuộc -> rốt cuộc)
REALWORD_CONFUSABLES = {
    "khôn": ["không"],
    "suột": ["ruột"],
    "xuông": ["vuông"],
    "dep": ["dẹp"],
    "ghĩ": ["nghĩ"],
    "sẫn": ["sân"],
    "rút cuộc": ["rốt cuộc"],
    "rút cục": ["rốt cục"]
}

# Quy tắc Collocation kiểm tra cụm 2 từ
COLLOCATIONS = {
    "sốt": {"ruột": 10},
    "khăn": {"vuông": 10},
    "dọn": {"dẹp": 10},
    "ngẫm": {"nghĩ": 10},
    "trang": {"phục": 10, "trí": 10, "bị": 10, "web": 10, "trường": 10, "điểm": 10},
    "tra": {"khảo": 10, "cứu": 10, "hỏi": 10, "dầu": 10, "hạt": 10}
}

# Whitelist các từ mượn phổ thông (Đã thêm carton, video, laptop, zal)
LOANWORD_WHITELIST = {
    "hamster", "pizza", "email", "ok", "docx", "python", "ai", "deepseek",
    "stent", "nilon", "nylon", "jeans", "hoodie", "chat", "inox", "teen", "ừm", "sofa",
    "carton", "catton", "video", "audio", "zalo", "facebook", "laptop", "polyester",
    "cardigan", "blazer", "tivi", "radar", "vaccine", "virus", "fan", "fanpage"
}

QWERTY_NEIGHBORS = {
    "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "ersfcx", "e": "wsdr",
    "f": "rtdvcb", "g": "tyfbhn", "h": "yugjbn", "i": "ujko", "k": "ijlm",
    "l": "okp", "m": "njk", "n": "bhjm", "o": "iklp", "p": "ol",
    "q": "wa", "r": "edft", "s": "wedxza", "t": "rfgy", "u": "yhji",
    "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx"
}
