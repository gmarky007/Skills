# -*- coding: utf-8 -*-
"""
Vietnamese Spell Checker Pipeline — vn_spell_checker.py
Pipeline kiểm tra chính tả tiếng Việt 6 giai đoạn (Từ điển + DeepSeek AI VIP Pro).

Usage:
    python vn_spell_checker.py "path/to/file.docx"
    python vn_spell_checker.py "path/to/file.docx" --deepseek
    python vn_spell_checker.py "path/to/file.docx" --mode hybrid --fix
"""

import os
import re
import sys
import io
import argparse
import unicodedata
from collections import Counter

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ---------------------------------------------------------------------------
# Imports — thư viện bên ngoài
# ---------------------------------------------------------------------------
try:
    import underthesea
    HAS_UNDERTHESEA = True
except ImportError:
    HAS_UNDERTHESEA = False

try:
    import docx as python_docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# ---------------------------------------------------------------------------
# Import confusable pairs database (cùng thư mục scripts/)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
try:
    from confusable_pairs import (
        HOI_NGA_MAP,
        REALWORD_CONFUSABLES,
        COLLOCATIONS,
        LOANWORD_WHITELIST,
        QWERTY_NEIGHBORS,
    )
except ImportError:
    HOI_NGA_MAP = {"ả": "ã", "ã": "ả", "ẩ": "ẫ", "ẫ": "ẩ", "ẳ": "ẵ", "ẵ": "ẳ", "ẻ": "ẽ", "ẽ": "ẻ", "ể": "ễ", "ễ": "ể", "ỉ": "ĩ", "ĩ": "ỉ", "ỏ": "õ", "õ": "ỏ", "ổ": "ỗ", "ỗ": "ổ", "ở": "ỡ", "ỡ": "ở", "ủ": "ũ", "ũ": "ủ", "ử": "ữ", "ữ": "ử", "ỷ": "ỹ", "ỹ": "ỷ"}
    REALWORD_CONFUSABLES = {
        "khôn": ["không"], "tra": ["trang"], "suột": ["ruột"], "xuông": ["vuông"], "dep": ["dẹp"], "ghĩ": ["nghĩ"], "sẫn": ["sân"]
    }
    COLLOCATIONS = {
        "sốt": {"ruột": 10}, "khăn": {"vuông": 10}, "dọn": {"dẹp": 10}, "ngẫm": {"nghĩ": 10}
    }
    LOANWORD_WHITELIST = {"hamster", "pizza", "email", "ok", "docx", "python", "ai", "deepseek"}
    QWERTY_NEIGHBORS = {"a": "qwsz", "b": "vghn", "c": "xdfv", "d": "ersfcx", "e": "wsdr", "f": "rtdvcb", "g": "tyfbhn", "h": "yugjbn", "i": "ujko", "k": "ijlm", "l": "okp", "m": "njk", "n": "bhjm", "o": "iklp", "p": "ol", "q": "wa", "r": "edft", "s": "wedxza", "t": "rfgy", "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx"}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DICT_URL = "https://raw.githubusercontent.com/duyet/vietnamese-wordlist/master/Viet74K.txt"
VN_CHARS = r"a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ"

# DeepSeek API Configuration (Saved for Skill /chinhta)
DEFAULT_AI_KEY = "sk-5bb531362f1b43e49fb9034ce7d6bb1c"
DEFAULT_AI_MODEL = "deepseek-chat"
DEFAULT_AI_URL = "https://api.deepseek.com/chat/completions"


# ===========================================================================
# UTILITY FUNCTIONS
# ===========================================================================

def nfc(text: str) -> str:
    """Chuẩn hoá Unicode NFC."""
    return unicodedata.normalize("NFC", text)


def load_dictionary(workspace_dir: str) -> set:
    """Tải từ điển tổng hợp VietDictionary_Master (78.258 từ & từ ghép chuẩn)."""
    master_path = os.path.join(workspace_dir, "VietDictionary_Master.txt")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    master_path_script = os.path.join(script_dir, "VietDictionary_Master.txt")
    dict_path = os.path.join(workspace_dir, "Viet74K.txt")

    target_path = master_path if os.path.exists(master_path) else (master_path_script if os.path.exists(master_path_script) else dict_path)

    # Tải về Viet74K nếu chưa có
    if not os.path.exists(target_path) and not os.path.exists(dict_path):
        print(f"[INFO] Đang tải từ điển từ {DICT_URL} ...")
        import urllib.request
        req = urllib.request.Request(DICT_URL, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req).read()
        with open(dict_path, "wb") as f:
            f.write(data)
        target_path = dict_path

    syllables: set[str] = set()
    with open(target_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for word in re.split(r"[\s\-]+", line):
                cleaned = re.sub(rf"[^{VN_CHARS}]", "", word)
                if cleaned:
                    syllables.add(nfc(cleaned.lower()))

    # Thêm whitelist
    for w in LOANWORD_WHITELIST:
        syllables.add(nfc(w.lower()))

    return syllables


def read_docx(path: str) -> list[str]:
    """Đọc file .docx, trả về danh sách đoạn văn."""
    if not HAS_DOCX:
        raise ImportError("Cần cài thư viện python-docx: pip install python-docx")
    doc = python_docx.Document(path)
    return [p.text for p in doc.paragraphs]


def tokenize_words(text: str) -> list[str]:
    """Tách câu thành danh sách từ (âm tiết)."""
    return re.findall(r"\b\w+\b", text)


def is_vietnamese_word(word: str) -> bool:
    """Kiểm tra xem từ có chứa ký tự tiếng Việt không."""
    return bool(re.search(rf"[{VN_CHARS}]", word, re.IGNORECASE))


def is_capitalized(word: str) -> bool:
    """Kiểm tra từ viết hoa (tên riêng)."""
    return len(word) > 0 and word[0].isupper()


# ===========================================================================
# STAGE 1: DICTIONARY CHECK (Kiểm tra từ điển)
# ===========================================================================

def stage1_dictionary_check(paragraphs: list[str], valid_syllables: set) -> list[dict]:
    """
    STAGE 1 — Tra từ điển.
    Gắn cờ các từ KHÔNG có trong từ điển, KHÔNG phải tên riêng,
    KHÔNG phải số, KHÔNG phải từ mượn.
    """
    errors = []
    for idx, para in enumerate(paragraphs):
        if not para.strip():
            continue
        words = tokenize_words(para)
        for word in words:
            if re.search(r"\d", word):
                continue
            w_nfc = nfc(word.lower())
            if w_nfc in valid_syllables:
                continue
            if is_capitalized(word):
                continue
            if not is_vietnamese_word(word):
                continue

            errors.append({
                "stage": 1,
                "type": "NON_WORD",
                "paragraph": idx,
                "word": word,
                "suggestion": "",
                "context": para,
                "severity": "HIGH",
            })
    return errors


# ===========================================================================
# STAGE 2: TYPING ERROR DETECTION (Phát hiện lỗi gõ phím)
# ===========================================================================

def _detect_doubled_consonant(word: str) -> str | None:
    """Phát hiện phụ âm lặp: nngẫm → ngẫm."""
    m = re.search(r"([bcdfghklmnpqrstvxzđ])\1", word.lower())
    if m:
        return word.lower().replace(m.group(0), m.group(1), 1)
    return None


def _detect_stuck_words(word: str) -> str | None:
    """Phát hiện dính chữ: vàngchạy → vàng chạy."""
    if len(word) > 7:
        vowels_with_tone = re.findall(r"[áàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", word.lower())
        if len(vowels_with_tone) >= 2:
            return None
    return None


def _detect_keyboard_mistype(word: str, valid_syllables: set) -> str | None:
    """Phát hiện gõ lệch phím QWERTY: sra → ra, angh → anh."""
    w = word.lower()
    for i in range(len(w)):
        candidate = w[:i] + w[i+1:]
        if candidate and nfc(candidate) in valid_syllables:
            return candidate
    for i, ch in enumerate(w):
        neighbors = QWERTY_NEIGHBORS.get(ch, "")
        for nb in neighbors:
            candidate = w[:i] + nb + w[i+1:]
            if nfc(candidate) in valid_syllables:
                return candidate
    return None


def stage2_typing_errors(paragraphs: list[str], valid_syllables: set) -> list[dict]:
    """
    STAGE 2 — Phát hiện lỗi gõ phím.
    """
    errors = []
    for idx, para in enumerate(paragraphs):
        if not para.strip():
            continue
        words = tokenize_words(para)
        for word in words:
            if re.search(r"\d", word):
                continue
            w_nfc = nfc(word.lower())
            if w_nfc in valid_syllables:
                continue
            if is_capitalized(word):
                continue

            fix = _detect_doubled_consonant(word)
            if fix and nfc(fix) in valid_syllables:
                errors.append({
                    "stage": 2, "type": "DOUBLED_CONSONANT",
                    "paragraph": idx, "word": word,
                    "suggestion": fix, "context": para,
                    "severity": "HIGH",
                })
                continue

            if len(word) > 7:
                toned = re.findall(
                    r"[áàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
                    word.lower()
                )
                if len(toned) >= 2:
                    errors.append({
                        "stage": 2, "type": "STUCK_WORDS",
                        "paragraph": idx, "word": word,
                        "suggestion": "(cần thêm dấu cách)",
                        "context": para, "severity": "HIGH",
                    })
                    continue

            fix = _detect_keyboard_mistype(word, valid_syllables)
            if fix:
                errors.append({
                    "stage": 2, "type": "KEYBOARD_MISTYPE",
                    "paragraph": idx, "word": word,
                    "suggestion": fix, "context": para,
                    "severity": "MEDIUM",
                })
    return errors


# ===========================================================================
# STAGE 3: PHONETIC CONFUSION (Lỗi phát âm vùng miền)
# ===========================================================================

def _generate_hoi_nga_variants(word: str) -> list[str]:
    """Sinh các biến thể hỏi↔ngã của một từ."""
    variants = []
    for i, ch in enumerate(word):
        if ch in HOI_NGA_MAP:
            variant = word[:i] + HOI_NGA_MAP[ch] + word[i+1:]
            variants.append(variant)
    return variants


def stage3_phonetic_confusion(paragraphs: list[str], valid_syllables: set) -> list[dict]:
    """
    STAGE 3 — Phát hiện lỗi phát âm vùng miền.
    """
    errors = []
    for idx, para in enumerate(paragraphs):
        if not para.strip():
            continue
        words = tokenize_words(para)
        for word in words:
            if re.search(r"\d", word):
                continue
            w_nfc = nfc(word.lower())
            if w_nfc in valid_syllables:
                continue
            if is_capitalized(word):
                continue

            for variant in _generate_hoi_nga_variants(w_nfc):
                if nfc(variant) in valid_syllables:
                    errors.append({
                        "stage": 3, "type": "HOI_NGA_CONFUSION",
                        "paragraph": idx, "word": word,
                        "suggestion": variant,
                        "context": para, "severity": "HIGH",
                    })
                    break
    return errors


# ===========================================================================
# STAGE 4: CONTEXT CHECK — Real-word Errors (Lỗi ngữ cảnh)
# ===========================================================================

def stage4_context_check(paragraphs: list[str], valid_syllables: set) -> list[dict]:
    """
    STAGE 4 — Phát hiện lỗi real-word bằng N-gram & Collocation.
    """
    errors = []

    for idx, para in enumerate(paragraphs):
        if not para.strip():
            continue
        words = tokenize_words(para)

        for i, word in enumerate(words):
            w_nfc = nfc(word.lower())

            if w_nfc not in REALWORD_CONFUSABLES:
                continue

            candidates = REALWORD_CONFUSABLES[w_nfc]
            if not candidates:
                continue

            prev_word = nfc(words[i-1].lower()) if i > 0 else ""
            next_word = nfc(words[i+1].lower()) if i < len(words) - 1 else ""

            best_candidate = None
            best_score = 0

            if prev_word in COLLOCATIONS:
                col = COLLOCATIONS[prev_word]
                for cand in candidates:
                    if cand in col and col[cand] > best_score:
                        best_score = col[cand]
                        best_candidate = cand
                if w_nfc not in col and best_candidate and best_candidate != w_nfc:
                    errors.append({
                        "stage": 4, "type": "REALWORD_COLLOCATION",
                        "paragraph": idx, "word": word,
                        "suggestion": best_candidate,
                        "context": para, "severity": "HIGH",
                        "detail": f"Collocation: '{prev_word}' + '{best_candidate}' (score={best_score})",
                    })
                    continue

            if i >= 2:
                bigram_key = nfc(words[i-2].lower()) + "_" + prev_word
                if bigram_key in COLLOCATIONS:
                    col = COLLOCATIONS[bigram_key]
                    for cand in candidates:
                        if cand in col and col[cand] > best_score:
                            best_score = col[cand]
                            best_candidate = cand
                    if w_nfc not in col and best_candidate and best_candidate != w_nfc:
                        errors.append({
                            "stage": 4, "type": "REALWORD_COLLOCATION",
                            "paragraph": idx, "word": word,
                            "suggestion": best_candidate,
                            "context": para, "severity": "HIGH",
                            "detail": f"Bigram collocation: '{bigram_key}' + '{best_candidate}' (score={best_score})",
                        })
                        continue

            if w_nfc not in valid_syllables:
                for cand in candidates:
                    if nfc(cand) in valid_syllables and cand != w_nfc:
                        errors.append({
                            "stage": 4, "type": "REALWORD_NOT_IN_DICT",
                            "paragraph": idx, "word": word,
                            "suggestion": cand,
                            "context": para, "severity": "MEDIUM",
                        })
                        break

    return errors


# ===========================================================================
# STAGE 5: REPORT GENERATION (Tạo báo cáo)
# ===========================================================================

def _truncate_context(context: str, word: str, max_len: int = 120) -> str:
    """Cắt ngữ cảnh cho vừa bảng."""
    pos = context.lower().find(word.lower())
    if pos == -1:
        return context[:max_len] + "..."
    start = max(0, pos - 40)
    end = min(len(context), pos + len(word) + 40)
    snippet = context[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(context):
        snippet = snippet + "..."
    return snippet


def stage5_report(all_errors: list[dict], total_paragraphs: int,
                  output_path: str | None = None) -> str:
    """STAGE 5 — Tạo báo cáo Markdown."""
    type_counts = Counter(e["type"] for e in all_errors)
    stage_counts = Counter(e["stage"] for e in all_errors)

    lines = [
        "# 📋 Báo cáo Kiểm tra Chính tả Tiếng Việt",
        "",
        "## Tổng quan",
        f"- **Tổng số đoạn văn:** {total_paragraphs}",
        f"- **Tổng số lỗi phát hiện:** {len(all_errors)}",
        f"  - Stage 1 — Lỗi phi từ (Non-word): {stage_counts.get(1, 0)}",
        f"  - Stage 2 — Lỗi gõ phím (Typing): {stage_counts.get(2, 0)}",
        f"  - Stage 3 — Lỗi phát âm (Phonetic): {stage_counts.get(3, 0)}",
        f"  - Stage 4 — Lỗi ngữ cảnh (Real-word): {stage_counts.get(4, 0)}",
        f"  - Stage 6 — Lỗi AI DeepSeek (VIP Pro): {stage_counts.get(6, 0)}",
        "",
    ]

    if not all_errors:
        lines.append("> [!TIP]")
        lines.append("> Không phát hiện lỗi chính tả nào. Văn bản sạch!")
        report = "\n".join(lines)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
        return report

    lines.append("## Phân loại lỗi")
    lines.append("")
    lines.append("| Loại lỗi | Số lượng |")
    lines.append("| :--- | :---: |")
    type_labels = {
        "NON_WORD": "Không có trong từ điển",
        "DOUBLED_CONSONANT": "Phụ âm lặp (gõ phím)",
        "STUCK_WORDS": "Dính chữ (thiếu dấu cách)",
        "KEYBOARD_MISTYPE": "Gõ lệch phím QWERTY",
        "HOI_NGA_CONFUSION": "Nhầm hỏi/ngã",
        "REALWORD_COLLOCATION": "Sai ngữ cảnh (Collocation)",
        "REALWORD_NOT_IN_DICT": "Real-word + không trong từ điển",
        "REALWORD_CONTEXT": "Sai ngữ cảnh (DeepSeek AI)",
        "TONE_MARK": "Lỗi dấu thanh (DeepSeek AI)",
        "TYPO_TELEX": "Lỗi Telex/QWERTY (DeepSeek AI)",
        "REGIONAL_DIALECT": "Lỗi phát âm vùng miền (DeepSeek AI)"
    }
    for t, count in type_counts.most_common():
        label = type_labels.get(t, t)
        lines.append(f"| {label} | {count} |")
    lines.append("")

    lines.append("## Chi tiết lỗi")
    lines.append("")
    lines.append("| # | Đoạn | Từ sai | Loại lỗi | Đề xuất sửa | Mức độ | Ngữ cảnh |")
    lines.append("| :---: | :---: | :--- | :--- | :--- | :---: | :--- |")

    for i, e in enumerate(all_errors, 1):
        label = type_labels.get(e["type"], e["type"])
        ctx = _truncate_context(e["context"], e["word"])
        ctx = ctx.replace("|", "\\|").replace("\n", " ")
        sug = e.get("suggestion", "")
        sev = e.get("severity", "")
        lines.append(
            f"| {i} | {e['paragraph']} | `{e['word']}` | {label} | `{sug}` | {sev} | {ctx} |"
        )
    lines.append("")

    report = "\n".join(lines)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[INFO] Báo cáo đã lưu tại: {output_path}")

    return report


# ===========================================================================
# STAGE 6: DEEPSEEK AI LLM SPELL CHECK
# ===========================================================================

def stage6_ai_check(paragraphs: list[str], api_key: str = DEFAULT_AI_KEY, model_name: str = DEFAULT_AI_MODEL, api_url: str = DEFAULT_AI_URL) -> list[dict]:
    """Kiểm tra chính tả nâng cao bằng DeepSeek LLM API (12 nhóm lỗi chuẩn hoá + JSON Schema)."""
    import urllib.request
    import json
    import time
    from urllib.error import HTTPError

    valid_paras = [(i, p.strip()) for i, p in enumerate(paragraphs) if p.strip()]
    if not valid_paras:
        return []

    words_per_chunk = 2500
    chunks = []
    curr_chunk = []
    curr_count = 0
    
    for para_idx, p_text in valid_paras:
        item_str = f"[P{para_idx + 1}] {p_text}"
        w_len = len(p_text.split())
        if curr_count + w_len > words_per_chunk and curr_chunk:
            chunks.append(curr_chunk)
            curr_chunk = [(para_idx, item_str)]
            curr_count = w_len
        else:
            curr_chunk.append((para_idx, item_str))
            curr_count += w_len
    if curr_chunk:
        chunks.append(curr_chunk)

    ai_errors = []

    print(f"[STAGE 6 - DEEPSEEK AI CACHE-OPTIMIZED] Đang quét {len(valid_paras):,} đoạn văn qua model {model_name} ({len(chunks)} chunks)...", flush=True)

    # System Prompt chứa 100% TĨNH (Toàn bộ 12 quy tắc + Few-Shot + JSON Schema) để đạt Cache Hit >90%
    system_prompt = """Bạn là SIÊU CHUYÊN GIA HIỆU ĐÍNH TIẾNG VIỆT (Vietnamese Proofreading Expert).

MỤC TIÊU:
Phát hiện TẤT CẢ lỗi chính tả, lỗi đánh máy, lỗi ngữ cảnh, lỗi dấu câu và lỗi dùng từ trong văn bản tiếng Việt. KHÔNG ĐƯỢC BỎ SÓT BẤT KỲ LỖI NÀO.

12 NHÓM LỖI BẮT BUỘC RÀ SOÁT:
1. Lỗi đánh máy: Phụ âm lặp (khônng, nngẫm), nguyên âm lặp, gõ nhầm Telex/VNI (ghĩ, angh, laai), thừa/thiếu/đảo ký tự.
2. Lỗi dấu: Thiếu dấu thanh (dep -> dẹp, suot -> suốt), sai dấu thanh, nhầm hỏi/ngã (sẫn -> sân), nhầm sắc/huyền.
3. Lỗi khoảng trắng: Dính chữ (ngườita, vàngchạy, khôngcó), tách chữ sai (đượ c), thừa/thiếu khoảng trắng.
4. Lỗi chính tả vùng miền: tr/ch, s/x, d/gi/r, l/n, v/d, n/ng, t/c, i/y.
5. Lỗi âm cuối: n/ng, t/c, m/ng, p/t.
6. Lỗi Real-word (QUAN TRỌNG NHẤT): Từ đúng từ điển nhưng sai ngữ cảnh (khôn -> không, tra -> trang, sốt suột -> sốt ruột, khăn xuông -> khăn vuông, ngẫm ghĩ -> ngẫm nghĩ, dọn dep -> dọn dẹp).
7. Lỗi dùng sai từ: Ví dụ "tham quan học tập", "tham quan nghiên cứu".
8. Lỗi từ ghép: chia sẽ -> chia sẻ, sát nhập -> sáp nhập, xát sao -> sát sao.
9. Lỗi từ láy: lấp lánh, lung linh...
10. Lỗi dấu câu: phẩy, chấm, hai chấm, chấm phẩy, ngoặc, ngoặc kép, ba chấm.
11. Lỗi viết hoa: đầu câu, tên riêng, địa danh, cơ quan, chức danh.
12. Lỗi tiếng Anh: Chỉ bắt lỗi nếu từ tiếng Anh viết sai. Bỏ qua email, internet, pizza, hamster, Facebook, Google, ChatGPT.

NGOẠI LỆ (Không báo lỗi):
Tên người, địa danh, biệt danh, mã sản phẩm, URL, email, số điện thoại, mã code, ký hiệu kỹ thuật.

ĐỊNH DẠNG TRẢ VỀ:
CHỈ TRẢ VỀ JSON ARRAY. Không giải thích ngoài JSON.
Mẫu item:
[
  {
    "doan_so": 1,
    "original": "khônng",
    "suggestion": "không",
    "type": "typing",
    "rule": "double_consonant",
    "confidence": 0.99,
    "context": "Tôi khônng biết"
  }
]
Nếu KHÔNG có lỗi thì trả về đúng: []"""

    for chunk_idx, chunk_items in enumerate(chunks, 1):
        chunk_text = "\n".join([item[1] for item in chunk_items])
        print(f"[STAGE 6 - DEEPSEEK AI] [{chunk_idx}/{len(chunks)}] Đang rà soát chunk {chunk_idx}/{len(chunks)}...", flush=True)
        
        # User prompt giữ nguyên cấu trúc cố định ở đầu, đưa dữ liệu động {chunk_text} xuống cuối để tối ưu DeepSeek Prefix Cache Hit
        prompt = f"""Hãy rà soát kỹ văn bản dưới đây và trả về danh sách lỗi theo đúng 12 nhóm quy tắc trên:

\"\"\"
{chunk_text}
\"\"\""""

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': f'Bearer {api_key}'
        }
        req = urllib.request.Request(api_url, data=data, headers=headers)

        for attempt in range(4):
            try:
                with urllib.request.urlopen(req) as resp:
                    res = json.loads(resp.read().decode('utf-8'))
                    usage = res.get('usage', {})
                    cache_hit = usage.get('prompt_cache_hit_tokens', 0)
                    cache_miss = usage.get('prompt_cache_miss_tokens', 0)

                    raw_out = res['choices'][0]['message']['content'].strip()
                    if raw_out.startswith("```json"): raw_out = raw_out[7:]
                    if raw_out.startswith("```"): raw_out = raw_out[3:]
                    if raw_out.endswith("```"): raw_out = raw_out[:-3]
                    
                    parsed = json.loads(raw_out.strip())
                    for item in parsed:
                        p_idx = item.get("doan_so", 1) - 1
                        ai_errors.append({
                            "stage": 6,
                            "paragraph": p_idx,
                            "word": item.get("original", item.get("tu_sai", "")),
                            "type": item.get("type", item.get("loai_loi", "DEEPSEEK_AI")),
                            "suggestion": item.get("suggestion", item.get("de_xuat_sua", "")),
                            "severity": "HIGH",
                            "context": item.get("context", item.get("cau_goc", "")),
                            "detail": item.get("rule", "")
                        })
                    print(f"[STAGE 6 - DEEPSEEK AI] [{chunk_idx}/{len(chunks)}] Xử lý xong | Cache Hit: {cache_hit:,} tokens, Miss: {cache_miss:,} tokens | Phát hiện {len(parsed)} lỗi", flush=True)
                    break
            except HTTPError as e:
                print(f"[STAGE 6 - DEEPSEEK AI] [{chunk_idx}/{len(chunks)}] HTTP Error {e.code}, thử lại lần {attempt+1}/4...", flush=True)
                if e.code == 429:
                    time.sleep((attempt + 1) * 3)
                else:
                    time.sleep(2)
            except Exception as e:
                print(f"[STAGE 6 - DEEPSEEK AI] [{chunk_idx}/{len(chunks)}] Lỗi: {e}, thử lại lần {attempt+1}/4...", flush=True)
                time.sleep(2)

        time.sleep(1.0)

    return ai_errors


def stage7_ollama_check(paragraphs: list[str], model_name: str = "qwen2.5:7b", ollama_url: str = "http://localhost:11434/api/chat", paras_per_chunk: int = 20, max_chunks: int = 0) -> list[dict]:
    """Kiểm tra chính tả bằng mô hình AI Local với Real-Time Streaming Logs (Ollama - 100% OFFLINE trên GPU)."""
    import urllib.request
    import json

    valid_paras = [(i, p.strip()) for i, p in enumerate(paragraphs) if p.strip()]
    if not valid_paras:
        return []

    chunks = []
    for i in range(0, len(valid_paras), paras_per_chunk):
        chunk_group = valid_paras[i:i + paras_per_chunk]
        chunk_items = [(idx, f"[P{idx + 1}] {text}") for idx, text in chunk_group]
        chunks.append(chunk_items)
        if max_chunks and len(chunks) >= max_chunks:
            break

    ai_errors = []
    print(f"[STAGE 7 - OLLAMA OFFLINE REALTIME] Đang quét {len(chunks)} chunks ({paras_per_chunk} câu/chunk, tổng {len(valid_paras)} câu) qua model {model_name}...", flush=True)

    system_prompt = """Bạn là SIÊU CHUYÊN GIA HIỆU ĐÍNH TIẾNG VIỆT (Vietnamese Spell Checker).

BẮT BUỘC CHỈ SỬA LỖI CHÍNH TẢ RÕ RÀNG:
1. Lỗi gõ phím/Telex: dep -> dẹp, laai -> lâu, khônng -> không, ghĩ -> nghĩ.
2. Lỗi dấu thanh/phát âm: sẫn -> sân, rút cuộc -> rốt cuộc.
3. Lỗi từ sai chính tả: rách toác -> rách toạc.

CẤM TUYỆT ĐỐI (VI PHẠM SẼ BỊ PHẠT):
- CẤM viết lại câu hay đổi văn phong.
- CẤM đổi từ đồng nghĩa: CẤM đổi 'người chị' thành 'chị mình', CẤM đổi 'nhưng' thành 'mà', CẤM đổi 'tớ' thành 'tôi'.
- CẤM chép lại cả câu vào trường 'original'. Trường 'original' CHỈ ĐƯỢC CHỨA TỪ BỊ LỖI CHÍNH TẢ!

VÍ DỤ MẪU:
Văn bản: "[P1] Nội thất tuy đã cũ nhưng được dọn dep rất gọn gàng. [P2] Vưu Tư Gia ngẩng đầu nhìn người chị."
Trả về JSON:
[
  {
    "doan_so": 1,
    "original": "dep",
    "suggestion": "dẹp",
    "type": "typing",
    "context": "dọn dep rất gọn gàng"
  }
]
(Ghi chú: [P2] 'người chị' không có lỗi chính tả nên KHÔNG ĐƯỢC BÁO LỖI).

Nếu văn bản không có lỗi chính tả rõ ràng, BẮT BUỘC TRẢ VỀ []."""

    for chunk_idx, chunk_items in enumerate(chunks, 1):
        chunk_text = "\n".join([item[1] for item in chunk_items])
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Rà soát chính tả văn bản:\n{chunk_text}"}
            ],
            "options": {
                "temperature": 0.0
            },
            "stream": False
        }

        try:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(ollama_url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                raw_out = res['message']['content'].strip()
                if "<think>" in raw_out:
                    raw_out = raw_out.split("</think>")[-1].strip()
                if raw_out.startswith("```json"): raw_out = raw_out[7:]
                if raw_out.startswith("```"): raw_out = raw_out[3:]
                if raw_out.endswith("```"): raw_out = raw_out[:-3]

                parsed = json.loads(raw_out.strip())
                for item in parsed:
                    p_idx = item.get("doan_so", 1) - 1
                    err_obj = {
                        "stage": 7,
                        "paragraph": p_idx,
                        "word": item.get("original", item.get("tu_sai", "")),
                        "type": item.get("type", "OLLAMA_LOCAL_AI"),
                        "suggestion": item.get("suggestion", item.get("de_xuat_sua", "")),
                        "severity": "HIGH",
                        "context": item.get("context", item.get("cau_goc", "")),
                        "detail": item.get("rule", "Local Ollama GPU")
                    }
                    ai_errors.append(err_obj)
                    print(f"🎯 [REALTIME] Từ sai: '{err_obj['word']}' -> Đề xuất sửa: '{err_obj['suggestion']}' | Câu gốc: \"{err_obj['context']}\"", flush=True)
                print(f"[STAGE 7 - OLLAMA REALTIME] [{chunk_idx}/{len(chunks)}] Xử lý xong (Phát hiện {len(parsed)} lỗi)", flush=True)
        except Exception as e:
            print(f"[STAGE 7 - OLLAMA REALTIME] [{chunk_idx}/{len(chunks)}] Lỗi: {e}", flush=True)

    return ai_errors


# ===========================================================================
# FIX: Tự động sửa lỗi trong file DOCX
# ===========================================================================

def auto_fix_docx(input_path: str, errors: list[dict], output_path: str):
    """Tự động sửa các lỗi và tô màu ĐỎ nổi bật cho từ được sửa trong file DOCX."""
    if not HAS_DOCX:
        raise ImportError("Cần cài python-docx: pip install python-docx")

    from docx.shared import RGBColor

    doc = python_docx.Document(input_path)

    fixable = [e for e in errors if e.get("suggestion")
               and e["suggestion"] != "(cần thêm dấu cách)"
               and e.get("severity") == "HIGH"]

    fix_count = 0
    for e in fixable:
        para_idx = e["paragraph"]
        old_word = e["word"]
        new_word = e["suggestion"]
        if para_idx < len(doc.paragraphs):
            p = doc.paragraphs[para_idx]
            for run in p.runs:
                if old_word in run.text:
                    run.text = run.text.replace(old_word, new_word)
                    run.font.color.rgb = RGBColor(255, 0, 0)
                    run.font.bold = True
                    fix_count += 1

    doc.save(output_path)
    print(f"[INFO] Đã sửa {fix_count} lỗi (đã tô màu ĐỎ nổi bật), lưu tại: {output_path}")


# ===========================================================================
# MAIN PIPELINE
# ===========================================================================

def run_pipeline(paragraphs: list[str], workspace_dir: str,
                 stages: list[int] | None = None,
                 ai_key: str = DEFAULT_AI_KEY,
                 ai_model: str = DEFAULT_AI_MODEL,
                 ai_url: str = DEFAULT_AI_URL,
                 ollama_model: str = "deepseek-r1:8b") -> list[dict]:
    """Chạy toàn bộ pipeline kiểm tra chính tả."""
    if stages is None:
        stages = [1, 2, 3, 4, 5]

    print("[PIPELINE] Đang tải từ điển...")
    valid_syllables = load_dictionary(workspace_dir)
    print(f"[PIPELINE] Đã tải {len(valid_syllables)} âm tiết hợp lệ.")

    all_errors: list[dict] = []

    if 1 in stages:
        print("[STAGE 1] Kiểm tra từ điển...")
        errs = stage1_dictionary_check(paragraphs, valid_syllables)
        print(f"  → Phát hiện {len(errs)} lỗi phi từ")
        all_errors.extend(errs)

    if 2 in stages:
        print("[STAGE 2] Phát hiện lỗi gõ phím...")
        errs = stage2_typing_errors(paragraphs, valid_syllables)
        print(f"  → Phát hiện {len(errs)} lỗi gõ phím")
        all_errors.extend(errs)

    if 3 in stages:
        print("[STAGE 3] Phát hiện lỗi phát âm vùng miền...")
        errs = stage3_phonetic_confusion(paragraphs, valid_syllables)
        print(f"  → Phát hiện {len(errs)} lỗi phát âm")
        all_errors.extend(errs)

    if 4 in stages:
        print("[STAGE 4] Phân tích ngữ cảnh (real-word errors)...")
        errs = stage4_context_check(paragraphs, valid_syllables)
        print(f"  → Phát hiện {len(errs)} lỗi ngữ cảnh")
        all_errors.extend(errs)

    if 6 in stages:
        errs = stage6_ai_check(paragraphs, ai_key, ai_model, ai_url)
        print(f"  → DeepSeek AI Cloud phát hiện {len(errs)} câu sai")
        all_errors.extend(errs)

    if 7 in stages:
        errs = stage7_ollama_check(paragraphs, ollama_model)
        print(f"  → Ollama Local AI GPU phát hiện {len(errs)} câu sai")
        all_errors.extend(errs)

    seen = set()
    unique_errors = []
    for e in all_errors:
        key = (e["paragraph"], e["word"], e.get("suggestion", ""))
        if key not in seen:
            seen.add(key)
            unique_errors.append(e)

    return unique_errors


def main():
    parser = argparse.ArgumentParser(
        description="Vietnamese Spell Checker Pipeline"
    )
    parser.add_argument("input", nargs="?", help="Đường dẫn file .docx")
    parser.add_argument("--text", type=str, help="Văn bản cần kiểm tra")
    parser.add_argument("--output", type=str, default="spelling_report.md",
                        help="Đường dẫn file báo cáo đầu ra")
    parser.add_argument("--fix", action="store_true",
                        help="Tự động sửa lỗi và xuất file .docx mới")
    parser.add_argument("--mode", type=str, choices=["offline", "api", "hybrid", "ollama"], default=None,
                        help="Chọn chế độ: 'offline' (Local 5-stage), 'api' (DeepSeek AI Cloud), 'ollama' (DeepSeek-R1 8B Local GPU), hoặc 'hybrid'")
    parser.add_argument("--stages", type=str, default="1,2,3,4,5",
                        help="Chọn giai đoạn chạy, vd: 1,2,4,7")
    parser.add_argument("--deepseek", "--ai", action="store_true",
                        help="Kích hoạt kiểm tra chính tả bằng DeepSeek AI Cloud")
    parser.add_argument("--ollama", action="store_true",
                        help="Kích hoạt kiểm tra chính tả 100%% OFFLINE bằng Ollama Local GPU (qwen2.5:7b)")
    parser.add_argument("--ollama-model", type=str, default="qwen2.5:7b",
                        help="Ollama Model Name")
    parser.add_argument("--api-key", type=str, default=DEFAULT_AI_KEY,
                        help="AI API Key")
    parser.add_argument("--model", type=str, default=DEFAULT_AI_MODEL,
                        help="AI Model")
    parser.add_argument("--url", type=str, default=DEFAULT_AI_URL,
                        help="AI API URL Endpoint")

    args = parser.parse_args()

    if args.mode == "offline":
        stages = [1, 2, 3, 4, 5]
    elif args.mode == "api":
        stages = [6, 5]
    elif args.mode == "ollama":
        stages = [7, 5]
    elif args.mode == "hybrid":
        stages = [1, 2, 3, 4, 7, 5]
    else:
        stages = [int(s.strip()) for s in args.stages.split(",")]
        if args.deepseek and 6 not in stages:
            stages.append(6)
        if args.ollama and 7 not in stages:
            stages.append(7)

    import time
    start_time = time.time()

    if args.input:
        workspace_dir = os.path.dirname(os.path.abspath(args.input))
    else:
        workspace_dir = os.getcwd()

    if args.text:
        paragraphs = args.text.split("\n")
        input_path = None
    elif args.input:
        input_path = args.input
        if input_path.endswith(".docx"):
            paragraphs = read_docx(input_path)
        else:
            with open(input_path, "r", encoding="utf-8") as f:
                paragraphs = f.readlines()
    else:
        parser.print_help()
        sys.exit(1)

    print(f"[PIPELINE] Đầu vào: {len(paragraphs)} đoạn văn")

    errors = run_pipeline(paragraphs, workspace_dir, stages,
                          ai_key=args.api_key, ai_model=args.model, ai_url=args.url,
                          ollama_model=args.ollama_model)

    if 5 in stages:
        print("[STAGE 5] Tạo báo cáo...")
        report = stage5_report(errors, len(paragraphs), args.output)
        print(report[:500])

    if args.fix and args.input and args.input.endswith(".docx"):
        fix_path = args.input.replace(".docx", " - spellchecked.docx")
        auto_fix_docx(args.input, errors, fix_path)

    elapsed_time = time.time() - start_time
    print(f"\n[PIPELINE] Hoàn tất trong {elapsed_time:.2f} giây ({elapsed_time/60:.2f} phút). Tổng số lỗi: {len(errors)}")


if __name__ == "__main__":
    main()
