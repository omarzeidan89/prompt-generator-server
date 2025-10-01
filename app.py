# app.py
# ============================================================
# AI Prompts Generator (AR/EN) — Production-grade single file
# Features:
# 1) Smart Hash Cache (exact + partial similarity) with Redis + local LRU
# 2) Token scaling by (language + type) + dynamic complexity
# 3) PreGPT Quick Rules (returns ready prompts w/o calling OpenAI)
# 4) Compact "Symbol" System Prompts to minimize tokens
# 5) Heuristic intent detection (AR/EN) if type is missing
# 6) Rate limiting + CORS + Health endpoint
# ------------------------------------------------------------
# Env:
#   OPENAI_API_KEY  (required)
#   REDIS_URL       (optional, defaults to redis://localhost:6379)
# ============================================================

import os
import re
import time
import json
import math
import hashlib
import logging
import unicodedata
from difflib import SequenceMatcher
from collections import deque

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import redis
import openai

# ------------ Basic Setup ------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# بعض المنصات تحقن بروكسيات تؤثر على OpenAI؛ تفريغها احترازيًا
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)
CORS(app)

# Rate limiting (عدلها حسب احتياجك)
limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

# Redis (اختياري)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
cache = None
try:
    cache = redis.from_url(REDIS_URL)
    cache.ping()
    logging.info("✅ Redis connected")
except Exception as e:
    logging.warning(f"⚠️ Redis not available: {e}")
    cache = None

# ------------ Cache Controls ------------
CACHE_NS = "pg"  # namespace
CACHE_KEYS_LIST = f"{CACHE_NS}:keys"     # list of recent cache keys
CACHE_META_PREFIX = f"{CACHE_NS}:meta:"  # meta per key (stores norm text/type/lang)
CACHE_VAL_PREFIX = f"{CACHE_NS}:val:"    # value per key (the prompt)
CACHE_KEYS_MAX = 2000                    # scan window for similarity
CACHE_TTL_DEFAULT = 7 * 24 * 3600        # 7 days

# In-memory micro LRU booster
LOCAL_LRU_MAX = 256
local_lru = deque(maxlen=LOCAL_LRU_MAX)
local_map = {}

# Forbidden brand words in outputs
FORBIDDEN = ["chatgpt", "openai", "midjourney", "dall", "google", "bard", "claude", "gpt"]

# ------------ Text Normalization (AR/EN) ------------
AR_DIACRITICS = re.compile(r'[\u064B-\u0652]')
PUNCT = re.compile(r'[^\w\s\u0600-\u06FF]')  # احتفظ بحروف العربية
MULTISPACE = re.compile(r'\s+')
AR_LETTERS = re.compile(r'[\u0600-\u06FF]')

def normalize_text(txt: str) -> str:
    t = txt.strip().lower()
    t = unicodedata.normalize("NFKC", t)
    t = AR_DIACRITICS.sub('', t)  # إزالة التشكيل
    t = PUNCT.sub(' ', t)         # إزالة معظم الرموز مع إبقاء العربية
    t = MULTISPACE.sub(' ', t)
    return t.strip()

def is_arabic_text(t: str) -> bool:
    return bool(AR_LETTERS.search(t))

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

# ------------ Smart Cache: exact + partial similarity ------------
def _local_lru_get(lk: str):
    if lk in local_map:
        try:
            local_lru.remove(lk)
        except ValueError:
            pass
        local_lru.append(lk)
        return local_map[lk]
    return None

def _local_lru_put(lk: str, val: str):
    if lk in local_map:
        try:
            local_lru.remove(lk)
        except ValueError:
            pass
    elif len(local_lru) >= LOCAL_LRU_MAX:
        oldest = local_lru.popleft()
        local_map.pop(oldest, None)
    local_lru.append(lk)
    local_map[lk] = val

def cache_store(norm_text: str, ptype: str, lang: str, prompt: str):
    """Store prompt in Redis (if available) and local LRU."""
    key = f"{ptype}|{lang}|{sha1(norm_text)}"
    _local_lru_put(key, prompt)
    if cache:
        pipe = cache.pipeline()
        pipe.setex(CACHE_VAL_PREFIX + key, CACHE_TTL_DEFAULT, prompt)
        meta = json.dumps({"norm": norm_text, "type": ptype, "lang": lang, "ts": time.time()})
        pipe.setex(CACHE_META_PREFIX + key, CACHE_TTL_DEFAULT, meta)
        pipe.lpush(CACHE_KEYS_LIST, key)
        pipe.ltrim(CACHE_KEYS_LIST, 0, CACHE_KEYS_MAX - 1)
        pipe.execute()
    return key

def cache_lookup(norm_text: str, ptype: str, lang: str, similarity_threshold: float = 0.86):
    """Lookup exact/partial similar prompt from cache."""
    key = f"{ptype}|{lang}|{sha1(norm_text)}"
    # 1) local exact
    v = _local_lru_get(key)
    if v is not None:
        return v

    # 2) redis exact
    if cache:
        v = cache.get(CACHE_VAL_PREFIX + key)
        if v:
            v = v.decode("utf-8")
            _local_lru_put(key, v)
            return v

        # 3) partial similarity scan (على آخر N مفاتيح فقط)
        keys = cache.lrange(CACHE_KEYS_LIST, 0, CACHE_KEYS_MAX - 1)
        best_k = None
        best_sim = 0.0
        for raw in keys:
            k = raw.decode("utf-8")
            # نفس النوع واللغة فقط
            if not k.startswith(f"{ptype}|{lang}|"):
                continue
            meta_raw = cache.get(CACHE_META_PREFIX + k)
            if not meta_raw:
                continue
            try:
                meta = json.loads(meta_raw.decode("utf-8"))
                prev_norm = meta.get("norm", "")
            except Exception:
                continue
            sim = SequenceMatcher(a=norm_text, b=prev_norm).ratio()
            if sim > best_sim:
                best_sim = sim
                best_k = k
        if best_k and best_sim >= similarity_threshold:
            v2 = cache.get(CACHE_VAL_PREFIX + best_k)
            if v2:
                v2 = v2.decode("utf-8")
                # خزنه محليًا تحت هاش هذا الإدخال لتحسين السرعة لاحقًا
                _local_lru_put(key, v2)
                return v2

    # 4) local partial fallback (لا يوجد ميتاداتا محلية كافية لدقة عالية)
    return None

# ------------ Heuristic Intent Detection (no extra API call) ------------
TYPE_ALIASES = {
    "نص": "text", "صورة": "image", "فيديو": "video", " كود": "code", "كود": "code",
    "text": "text", "image": "image", "video": "video", "code": "code"
}

def heuristic_intent(user_input: str):
    t = normalize_text(user_input)
    # كلمات مفتاحية بسيطة (AR/EN)
    image_kw = ["صورة", "ارسم", "لوحة", "مشهد", "image", "picture", "render", "art", "photo"]
    video_kw = ["فيديو", "مشهد سينمائي", "لقطة", "موشن", "video", "cinematic", "clip", "short"]
    code_kw  = ["كود", "برمجة", "بايثون", "جافاسكربت", "html", "css", "sql", "javascript", "python", "code", "function", "script"]

    low = user_input.lower()
    score_img = sum(1 for k in image_kw if k in low)
    score_vid = sum(1 for k in video_kw if k in low)
    score_cod = sum(1 for k in code_kw  if k in low)

    if score_cod >= max(score_img, score_vid) and score_cod > 0:
        return "code"
    if score_vid >= max(score_img, score_cod) and score_vid > 0:
        return "video"
    if score_img >= max(score_vid, score_cod) and score_img > 0:
        return "image"

    # fallback
    if user_input.strip().endswith((".py", ".js", ".html", ".css")):
        return "code"

    return "text"

# ------------ Token Scaling (language + type + complexity) ------------
# وفق الجدول الذي طلبته:
BASE_MAX_TOKENS = {
    ("ar", "image"): 400,
    ("en", "image"): 300,
    ("ar", "text"):  300,
    ("en", "text"):  200,
    ("ar", "video"): 400,
    ("en", "video"): 300,
    ("ar", "code"):  300,
    ("en", "code"):  250,
}

def estimate_complexity(user_text: str) -> float:
    """درجة تعقيد تقريبية [0..1] حسب الطول والبنية."""
    words = len(user_text.strip().split())
    punct = sum(1 for c in user_text if c in ",.;:!؟?!-()[]{}")
    score = 0.0
    score += min(words / 60.0, 0.5)         # 0..0.5
    score += min(punct / 8.0, 0.3)          # 0..0.3
    score += 0.2 if (" and " in user_text.lower() or " و " in user_text) else 0.0
    return min(score, 1.0)

def pick_max_tokens(language: str, ptype: str, user_text: str) -> int:
    lang = "ar" if language.lower().startswith("ar") or is_arabic_text(user_text) else "en"
    ptype = TYPE_ALIASES.get(ptype, ptype).lower()
    if ptype not in ["text", "image", "video", "code"]:
        ptype = heuristic_intent(user_text)

    base = BASE_MAX_TOKENS.get((lang, ptype), 120)
    c = estimate_complexity(user_text)
    # سماح +/- 25% بناءً على التعقيد (حول نقطة 0.5)
    delta = int(base * (0.25 * (c - 0.5)))  # c=1 => +12.5%, c=0 => -12.5%
    mt = max(60, base + delta)
    return mt

# ------------ PreGPT Quick Rules (zero-token generation) ------------
def quick_rules(user_text: str, language: str):
    """
    Return (prompt_text, inferred_type) or (None, None) if no rule matched.
    Covers:
      - Quotes
      - Motivational lines
      - Tweet about ...
      - Common code snippets (JS/Python/HTML)
      - Email apology
      - Job interview question
      - YouTube title prompt
    """
    txt = user_text.strip()
    low = txt.lower()
    is_ar = (language.lower().startswith("ar") or is_arabic_text(txt))

    # -------- Quotes / Motivational --------
    if any(k in low for k in ["quote", "اقتباس", "قول", "حكمة", "motivational", "inspire"]):
        if is_ar:
            return ("\"لا تنتظر الفرصة، اصنعها.\" — مجهول", "text")
        else:
            return ("\"Don’t wait for opportunity. Create it.\" — Unknown", "text")

    if any(k in low for k in ["حفزني", "تحفيز", "motivate", "motivation", "inspire me"]):
        if is_ar:
            return ("تذكّر: خطوة صغيرة يوميًا أقوى من انفجار حماس عابر. 👊", "text")
        else:
            return ("Remember: tiny daily steps beat occasional bursts of motivation. 👊", "text")

    # -------- Tweet about ... --------
    if any(k in low for k in ["اكتب تغريدة", "اكتب تويت", "write a tweet", "tweet about"]):
        topic = re.sub(r".*عن|about", "", txt, flags=re.IGNORECASE).strip() or "your topic"
        if is_ar:
            return (f"تغريدة عن {topic}:\n"
                    f"الفكرة ليست أن تعرف كل شيء، بل أن تبدأ بما تعرفه الآن. #تعلم #تطوير_ذاتي", "text")
        else:
            return (f"Tweet about {topic}:\n"
                    f"You don’t need to know everything to start—begin with what you have. #learning #building", "text")

    # -------- Common code snippets --------
    # JS sum two numbers
    if any(k in low for k in ["js", "javascript"]) and any(k in low for k in ["sum", "جمع", "add numbers", "جمع رقمين"]):
        code = "function add(a, b){ return a + b; }\nconsole.log(add(3, 5));"
        prompt = ("Write a JavaScript snippet to add two numbers and print the result:\n\n" + code)
        return (prompt if not is_ar else ("اكتب كود JavaScript لجمع رقمين وطباعتهما:\n\n" + code), "code")

    # Python quadratic solver
    if any(k in low for k in ["python", "بايثون"]) and ("quadratic" in low or "تربيعية" in low):
        code = (
            "import math\n"
            "def solve_quadratic(a,b,c):\n"
            "    d=b*b-4*a*c\n"
            "    if d<0: return None\n"
            "    r=math.sqrt(d)\n"
            "    return ((-b+r)/(2*a), (-b-r)/(2*a))\n"
            "print(solve_quadratic(1,-3,2))"
        )
        prompt = ("Write a Python function to solve a quadratic equation ax^2+bx+c=0:\n\n" + code)
        return (prompt if not is_ar else ("اكتب دالة بايثون لحل معادلة تربيعية ax^2+bx+c=0:\n\n" + code), "code")

    # HTML dropdown
    if "html" in low and any(k in low for k in ["dropdown", "قائمة منسدلة"]):
        code = (
            "<label for=\"color\">Choose color:</label>\n"
            "<select id=\"color\">\n"
            "  <option>Red</option>\n"
            "  <option>Green</option>\n"
            "  <option>Blue</option>\n"
            "</select>"
        )
        prompt = ("Create a simple HTML dropdown component:\n\n" + code)
        return (prompt if not is_ar else ("أنشئ قائمة منسدلة بسيطة بـ HTML:\n\n" + code), "code")

    # -------- Email apology --------
    if any(k in low for k in ["email apology", "اعتذار عبر الايميل", "ايميل اعتذار", "رسالة اعتذار"]):
        if is_ar:
            return ("اكتب قالب بريد إلكتروني اعتذاري احترافي:\n"
                    "العنوان: اعتذار عن التأخير\n"
                    "المتن: مرحبًا [الاسم]، أعتذر عن التأخير في الرد بسبب [السبب]. أقدّر وقتك وسأضمن عدم تكرار ذلك. شكرًا لتفهمك.\n"
                    "التوقيع: [اسمك]", "text")
        else:
            return ("Write a professional apology email template:\n"
                    "Subject: Apology for the delay\n"
                    "Body: Hi [Name], I apologize for my delayed response due to [reason]. I appreciate your time and will ensure this won’t happen again. Thank you for understanding.\n"
                    "Signature: [Your Name]", "text")

    # -------- Job interview question --------
    if any(k in low for k in ["job interview", "سؤال مقابلة", "مقابلة عمل"]):
        if is_ar:
            return ("سؤال مقابلة عمل: احك لي عن تحدٍ واجهته وكيف تعاملت معه.\n"
                    "نموذج إجابة: عرّف التحدي، اذكر دورك، الإجراءات، والنتيجة القابلة للقياس.", "text")
        else:
            return ("Job interview question: Tell me about a challenge you faced and how you handled it.\n"
                    "Model answer: define the challenge, your role, actions, and measurable outcome.", "text")

    # -------- YouTube title ideas --------
    if any(k in low for k in ["youtube title", "عنوان يوتيوب", "عنوان فيديو"]):
        topic = re.sub(r".*عن|about", "", txt, flags=re.IGNORECASE).strip() or "your topic"
        if is_ar:
            return (f"عناوين يوتيوب مقترحة عن {topic}:\n"
                    f"1) {topic}: السرّ الذي لا يخبرك به أحد\n"
                    f"2) {topic} في 10 دقائق — دليل عملي\n"
                    f"3) لماذا يفشل معظم الناس في {topic}؟", "text")
        else:
            return (f"YouTube title ideas about {topic}:\n"
                    f"1) {topic}: The Untold Secret\n"
                    f"2) {topic} in 10 Minutes — A Practical Guide\n"
                    f"3) Why Most People Fail at {topic}?", "text")

    return (None, None)

# ------------ Compact System Prompts (Symbols) ------------
SYS = {
    "P_TEXT_AR":  "دورك مهندس برومبتات. المهمة: صياغة برومبت نصي واضح وعملي، 50–150 كلمة، دون ذكر أسماء منصات.",
    "P_IMG_AR":   "مهندس برومبت صور. أنشئ وصفًا بصريًا غنيًا للمشهد (بيئة، إضاءة، ألوان، زاوية كاميرا، أسلوب)، 50–150 كلمة.",
    "P_VID_AR":   "مهندس برومبت فيديو. أنشئ وصفًا سينمائيًا قصيرًا (≈10 ثوانٍ) مع تفاصيل المشهد والمزاج والإيقاع.",
    "P_CODE_AR":  "مهندس برومبت كود. اطلب كودًا نظيفًا، محدد اللغة، مع تعليمات واضحة وملاحظات مختصرة.",
    "P_TEXT_EN":  "You are a prompt engineer. Produce a clear, actionable text prompt (50–150 words) without platform names.",
    "P_IMG_EN":   "Image prompt engineer. Create a rich visual description (environment, lighting, colors, camera angle, style), 50–150 words.",
    "P_VID_EN":   "Video prompt engineer. Create a short cinematic brief (~10s) detailing scene, mood, pacing.",
    "P_CODE_EN":  "Code prompt engineer. Request clean, language-specific code with concise comments and clear specs."
}

def pick_sys_prompt(lang: str, ptype: str) -> str:
    if lang == "ar":
        return {"text": SYS["P_TEXT_AR"], "image": SYS["P_IMG_AR"], "video": SYS["P_VID_AR"], "code": SYS["P_CODE_AR"]}[ptype]
    return {"text": SYS["P_TEXT_EN"], "image": SYS["P_IMG_EN"], "video": SYS["P_VID_EN"], "code": SYS["P_CODE_EN"]}[ptype]

# ------------ Output Cleanup ------------
FORBIDDEN_RE = re.compile("|".join(re.escape(w) for w in FORBIDDEN), flags=re.IGNORECASE)
def sanitize_output(s: str) -> str:
    return FORBIDDEN_RE.sub("AI tool", s).strip()

# ------------ Core Prompt Generation ------------
def generate_with_openai(user_text: str, language: str, ptype: str) -> str:
    if not OPENAI_API_KEY:
        return "Server misconfigured: OPENAI_API_KEY is missing."

    lang = "ar" if (language.lower().startswith("ar") or is_arabic_text(user_text)) else "en"
    ptype = TYPE_ALIASES.get(ptype, ptype).lower()
    if ptype not in ["text", "image", "video", "code"]:
        ptype = heuristic_intent(user_text)

    sys_msg = pick_sys_prompt(lang, ptype)
    max_toks = pick_max_tokens(lang, ptype, user_text)

    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_text.strip()}
        ],
        max_tokens=max_toks,
        temperature=0.7,
    )
    out = resp.choices[0].message["content"].strip()
    return sanitize_output(out)

# ------------ API Endpoint ------------
@app.route("/generate", methods=["POST"])
@limiter.limit("20 per minute")
def generate():
    """
    Request JSON:
      {
        "prompt": "user idea text",  # أو text أو input
        "type": "نص/صورة/فيديو/كود OR Text/Image/Video/Code (optional)",
        "language": "ar|en (optional)"
      }
    Response JSON:
      {
        "intent": "text|image|video|code",
        "language": "ar|en",
        "prompt": "generated prompt text",
        "cached": true|false,
        "rule_based": true|false
      }
    """
    data = request.get_json(force=True, silent=True) or {}

    # ✅ يدعم prompt/text/input كلها
    user_input = (data.get("prompt") or data.get("text") or data.get("input") or "").strip()

    req_type = (data.get("type") or "").strip()
    language = (data.get("language") or "").strip().lower()

    if not user_input:
        msg = "الرجاء إدخال نص صحيح" if (language.startswith("ar")) else "Please enter valid text"
        return jsonify({"error": msg}), 400

    # Detect language if not provided
    if not language:
        language = "ar" if is_arabic_text(user_input) else "en"

    # Canonicalize type or infer
    ptype = TYPE_ALIASES.get(req_type, req_type.lower()) if req_type else heuristic_intent(user_input)

    # -------- PreGPT Quick Rules (no OpenAI call) --------
    rule_prompt, rule_type = quick_rules(user_input, language)
    if rule_prompt:
        intent = rule_type if rule_type else ptype
        return jsonify({
            "intent": intent,
            "language": "ar" if language.startswith("ar") else "en",
            "prompt": rule_prompt,
            "cached": False,
            "rule_based": True
        })

    # -------- Smart Cache Lookup --------
    norm = normalize_text(user_input)
    cached = cache_lookup(norm, ptype, "ar" if language.startswith("ar") else "en")
    if cached:
        return jsonify({
            "intent": ptype,
            "language": "ar" if language.startswith("ar") else "en",
            "prompt": cached,
            "cached": True,
            "rule_based": False
        })

    # -------- OpenAI Generation --------
    prompt_text = generate_with_openai(user_input, language, ptype)

    # -------- Store in Cache --------
    cache_store(norm, ptype, "ar" if language.startswith("ar") else "en", prompt_text)

    return jsonify({
        "intent": ptype,
        "language": "ar" if language.startswith("ar") else "en",
        "prompt": prompt_text,
        "cached": False,
        "rule_based": False
    })

# ------------ Health ------------
@app.route("/health", methods=["GET"])
def health():
    ok = bool(OPENAI_API_KEY)
    redis_ok = False
    try:
        if cache:
            cache.ping()
            redis_ok = True
    except Exception:
        redis_ok = False
    return jsonify({
        "status": "ok" if ok else "missing_api_key",
        "redis": redis_ok,
        "lru_size": len(local_lru),
        "window_keys": CACHE_KEYS_MAX
    })

# ------------ Run ------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=5000)  # debug=False تلقائيًا

