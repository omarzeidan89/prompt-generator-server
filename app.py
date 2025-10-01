# app.py
import os, re, time, hashlib, logging
from collections import defaultdict
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis
import openai

# --- إعداد Logging احترافي ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# --- إعداد Flask ---
app = Flask(__name__)
CORS(app)

# --- Rate Limiting ---
limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

# --- إعداد OpenAI ---
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- إعداد Redis Cache ---
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    cache = redis.from_url(redis_url)
    cache.ping()
    logging.info("✅ Redis connected successfully!")
except Exception as e:
    cache = None
    logging.warning(f"⚠️ Redis not available: {e}")

# --- إعدادات الكاش ---
MAX_CACHE_SIZE = 2000
CACHE_STATS = defaultdict(int)

AI_NAME = "AI Prompts Generator"

CUSTOM_RESPONSES = {
    "ar": {
        "identity": f"أنا {AI_NAME}...",
        "purpose": "وظيفتي تحويل أفكارك إلى برومبتات احترافية.",
        "creator": "تم تصميمي بواسطة مطور عربي.",
        "how_work": "أحلل فكرتك وأحولها إلى برومبت واضح.",
        "capabilities": "يمكنني توليد برومبتات للنصوص، الصور، الفيديو، والكود.",
        "limitations": "لا أمتلك وعي أو مشاعر.",
        "privacy": "لا أخزن بياناتك. كل شيء يعالج بأمان."
    },
    "en": {
        "identity": f"I am {AI_NAME}...",
        "purpose": "My purpose is to turn your ideas into professional prompts.",
        "creator": "I was developed by an AI enthusiast.",
        "how_work": "I analyze your idea and turn it into a clear prompt.",
        "capabilities": "I can generate prompts for text, code, images, and videos.",
        "limitations": "I don’t have emotions or awareness.",
        "privacy": "I don’t store your data. Everything is secure."
    }
}

# --- دوال مساعدة ---
def is_identity_question(text: str) -> bool:
    patterns = [
        r"من أنت", r"who are you", r"ما اسمك", r"your name",
        r"من صنعك", r"who made you", r"developer", r"purpose",
        r"capabilities", r"limitations", r"privacy", r"chatgpt", r"gpt"
    ]
    return any(re.search(p, text.lower()) for p in patterns)

def get_custom_response(text: str, lang: str) -> str:
    responses = CUSTOM_RESPONSES.get(lang, CUSTOM_RESPONSES["en"])
    if "purpose" in text: return responses["purpose"]
    if "who" in text or "name" in text: return responses["identity"]
    return responses["identity"]

def generate_cache_key(text, ptype, lang):
    return hashlib.md5(f"{text}|{ptype}|{lang}".encode()).hexdigest()

def cache_get(key):
    if not cache: return None
    try:
        CACHE_STATS[key] += 1
        data = cache.get(key)
        return {"prompt": data.decode()} if data else None
    except Exception as e:
        logging.error(f"Cache error: {e}")
        return None

def cache_set(key, value, ttl=86400):
    if not cache: return
    try:
        cache.setex(key, ttl, value)
        if cache.dbsize() > MAX_CACHE_SIZE:
            logging.warning("⚠️ Cache full!")
    except Exception as e:
        logging.error(f"Cache set error: {e}")

# --- API ---
@app.route("/generate-prompt", methods=["POST"])
@limiter.limit("10 per 10 seconds")  # حماية إضافية
def generate_prompt():
    try:
        data = request.get_json(force=True)
        user_text = data.get("text", "").strip()
        ptype = data.get("type", "text")
        lang = data.get("language", "en")

        if not user_text:
            return jsonify({"error": "Please enter text!"}), 400

        # أسئلة الهوية
        if is_identity_question(user_text):
            return jsonify({"prompt": get_custom_response(user_text, lang)})

        # الكاش
        cache_key = generate_cache_key(user_text, ptype, lang)
        cached = cache_get(cache_key)
        if cached: return jsonify(cached)

        # system message
        system_prompt = "You are a professional AI prompt engineer."
        if lang == "ar":
            system_prompt = "أنت خبير في كتابة برومبتات احترافية للذكاء الاصطناعي."

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=250,
            temperature=0.8
        )

        result = response.choices[0].message["content"].strip()
        cache_set(cache_key, result)
        return jsonify({"prompt": result})

    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"error": "Server error, please try again later."}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "uptime": time.time(),
        "cache": bool(cache),
        "requests_cached": len(CACHE_STATS)
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
