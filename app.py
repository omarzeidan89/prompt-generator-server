# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import openai
import re
import redis
import hashlib
import time
from collections import defaultdict

# --- حل مشكلة proxies ---
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
# -------------------------

app = Flask(__name__)
CORS(app)

# مفتاح OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Redis Cache
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    cache = redis.from_url(redis_url)
    cache.ping()
    print("✅ Redis connected successfully!")
except Exception as e:
    cache = None
    print(f"⚠️ Redis not available: {e}")

MAX_CACHE_SIZE = 1000
CACHE_STATS = defaultdict(int)
AI_NAME = "AI Prompts Generator"

# ردود مخصصة
CUSTOM_RESPONSES = {
    "ar": {
        "identity": f"أنا {AI_NAME}، نموذج ذكاء اصطناعي لتوليد برومبتات احترافية.",
        "purpose": "وظيفتي هي تحويل أفكارك البسيطة إلى برومبتات دقيقة ومهنية.",
        "creator": "تم تصميمي بواسطة مطور عربي مهتم بالذكاء الاصطناعي.",
        "how_work": "أعمل عبر تحليل فكرتك وصياغتها بشكل يفهمه الذكاء الاصطناعي.",
        "capabilities": "يمكنني توليد برومبتات للنصوص، البرمجة، الصور والفيديو.",
        "limitations": "لا أمتلك وعي أو مشاعر، أنا أداة تقنية فقط.",
        "privacy": "لا أخزن مدخلاتك. كل شيء يعالج بأمان."
    },
    "en": {
        "identity": f"I am {AI_NAME}, an AI model designed to generate professional prompts.",
        "purpose": "My purpose is to turn your ideas into precise, professional prompts.",
        "creator": "I was developed by an Arabic-speaking AI enthusiast.",
        "how_work": "I analyze your idea and reframe it into a clear prompt.",
        "capabilities": "I can generate prompts for text, code, images, and videos.",
        "limitations": "I don’t have emotions or human-like awareness.",
        "privacy": "I don’t store your data. Everything is processed securely."
    }
}

# --- فلترة أسئلة الهوية ---
def is_identity_or_general_question(text):
    text_lower = text.lower().strip()
    patterns = [
        r"من أنت", r"مين أنت", r"ما اسمك", r"وش اسمك", r"who are you", r"your name",
        r"من صنعك", r"who made you", r"من مطورك", r"who developed you",
        r"ما هدفك", r"what is your purpose", r"why were you created",
        r"كيف تعمل", r"how do you work", r"قدراتك", r"capabilities",
        r"حدودك", r"limitations", r"خصوصيتي", r"privacy",
        r"chatgpt", r"openai", r"midjourney", r"dall", r"bard", r"claude", r"gpt"
    ]
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True
    return False

def get_custom_response(text, language="ar"):
    text_lower = text.lower().strip()
    if re.search(r"(من أنت|who are you|ما اسمك|your name)", text_lower):
        return CUSTOM_RESPONSES[language]["identity"]
    elif re.search(r"(ما هدفك|purpose)", text_lower):
        return CUSTOM_RESPONSES[language]["purpose"]
    elif re.search(r"(من صنعك|who made you)", text_lower):
        return CUSTOM_RESPONSES[language]["creator"]
    elif re.search(r"(كيف تعمل|how do you work)", text_lower):
        return CUSTOM_RESPONSES[language]["how_work"]
    elif re.search(r"(قدراتك|capabilities)", text_lower):
        return CUSTOM_RESPONSES[language]["capabilities"]
    elif re.search(r"(حدودك|limitations)", text_lower):
        return CUSTOM_RESPONSES[language]["limitations"]
    elif re.search(r"(خصوصيتي|privacy)", text_lower):
        return CUSTOM_RESPONSES[language]["privacy"]
    else:
        return CUSTOM_RESPONSES[language]["identity"]

# --- الكاش ---
def calculate_smart_expiry(prompt_text, request_count=1):
    prompt_length = len(prompt_text)
    length_factor = min(prompt_length / 100, 3)
    repeat_factor = min(request_count / 5, 4)
    base_time = 86400
    smart_expiry = int(base_time * length_factor * repeat_factor)
    return min(smart_expiry, 2592000)

def generate_cache_key(text, prompt_type, language):
    key_data = f"{text}|{prompt_type}|{language}"
    return hashlib.md5(key_data.encode()).hexdigest()

def get_from_cache(key):
    if cache is None:
        return None
    try:
        CACHE_STATS[key] += 1
        cached_data = cache.hgetall(f"prompt:{key}")
        if cached_data and b'prompt' in cached_data:
            return {"prompt": cached_data[b'prompt'].decode('utf-8')}
    except Exception as e:
        print(f"Cache get error: {e}")
    return None

def save_to_cache(key, value, prompt_text):
    if cache is None:
        return
    try:
        request_count = CACHE_STATS.get(key, 1)
        expiry = calculate_smart_expiry(prompt_text, request_count)
        cache.hset(f"prompt:{key}", mapping={
            'prompt': prompt_text,
            'timestamp': str(time.time()),
            'requests': str(request_count)
        })
        cache.expire(f"prompt:{key}", expiry)
        current_size = cache.dbsize()
        if current_size > MAX_CACHE_SIZE:
            print(f"⚠️ Cache size ({current_size}) exceeds limit.")
    except Exception as e:
        print(f"Cache set error: {e}")

# --- توليد البرومبت ---
@app.route('/generate-prompt', methods=['POST'])
def generate_prompt():
    try:
        data = request.get_json()
        user_text = data.get("text", "").strip()
        prompt_type = data.get("type", "text")
        language = data.get("language", "ar")

        if not user_text:
            return jsonify({"error": "الرجاء إدخال نص!" if language == "ar" else "Please enter text!"}), 400

        # أسئلة الهوية
        if is_identity_or_general_question(user_text):
            response_text = get_custom_response(user_text, language)
            return jsonify({"prompt": response_text})

        # إذا النص قصير جداً
        if len(user_text.split()) < 3:
            if language == "ar":
                user_text = f"أنشئ برومبت إبداعي حول: {user_text}. اجعله مليئاً بالتفاصيل والأسلوب الاحترافي."
            else:
                user_text = f"Create a professional AI prompt about: {user_text}. Add rich details and style."

        # تحقق من الكاش
        cache_key = generate_cache_key(user_text, prompt_type, language)
        cached_result = get_from_cache(cache_key)
        if cached_result:
            print("✅ Cache hit!")
            return jsonify(cached_result)

        # system prompt
        if language == "ar":
            base_system = """
أنت خبير محترف في كتابة البرومبتات الإبداعية لأدوات الذكاء الاصطناعي.
مهمتك: تحويل أي فكرة إلى برومبت احترافي واضح ومفصل.
قواعد:
- لا تكرر نص المستخدم حرفياً.
- اجعل البرومبت يوجه الأداة مباشرة.
- إذا كان الطلب غامضاً، أضف تفاصيل منطقية.
- لا تذكر أسماء منصات أو نماذج.
- النتيجة بين 50–150 كلمة.
"""
            type_instructions = {
                "text": "أعد صياغة الفكرة كبرومبت نصي احترافي للكتابة الإبداعية.",
                "image": "حوّل الفكرة إلى برومبت لتوليد الصور. صف المشهد بوضوح، مع تفاصيل عن البيئة، الإضاءة، الألوان، زاوية الكاميرا، والأسلوب الفني. لا تعتذر أبداً، فقط أنشئ وصفاً نصياً يصلح لمولدات الصور.",
                "code": "حوّل الطلب إلى برومبت كود نظيف ومعلق جيداً. حدد اللغة إن لم تذكر.",
                "video": "حوّل الفكرة إلى برومبت فيديو قصير (10 ثوانٍ) مع تفاصيل عن المشهد، الجو العام، والأسلوب."
            }
        else:
            base_system = """
You are a professional AI prompt engineer.
Your task: turn any idea into a high-quality, clear, detailed AI prompt.
Rules:
- Do not repeat the user's input literally.
- Make the prompt actionable and rich in details.
- If the request is vague, add reasonable details.
- Do not mention platforms or models.
- Output length: 50–150 words.
"""
            type_instructions = {
                "text": "Rewrite the idea as a creative text generation prompt.",
                "image": "Transform the idea into an image generation prompt. Describe the scene vividly with details about environment, lighting, colors, camera angle, and artistic style. Never apologize, always return a descriptive text prompt.",
                "code": "Turn the request into a coding prompt. Clean, efficient, well-commented code. Specify language if not provided.",
                "video": "Convert the idea into a cinematic 10-second video prompt. Include scene, mood, and style."
            }

        system_message = base_system + "\n\n" + type_instructions.get(prompt_type, type_instructions["text"])

        # ChatCompletion
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_text}
            ],
            max_tokens=250,
            temperature=0.8
        )

        generated_prompt = response.choices[0].message['content'].strip()

        # فلتر كلمات محظورة
        forbidden_words = ["chatgpt", "openai", "midjourney", "dall", "google", "bard", "claude", "gpt"]
        if any(word in generated_prompt.lower() for word in forbidden_words):
            generated_prompt = "تم توليد برومبت احترافي بنجاح." if language == "ar" else "A professional prompt has been generated successfully."

        result = {"prompt": generated_prompt}

        # حفظ بالكاش
        save_to_cache(cache_key, result, generated_prompt)
        print(f"💾 Cached! Key: {cache_key[:8]}...")

        return jsonify(result)

    except Exception as e:
        print(f"❌ Error: {e}")
        error_msg = "عذراً، حدث خطأ. حاول لاحقاً." if data.get("language", "ar") == "ar" else "Sorry, an error occurred. Please try again."
        return jsonify({"prompt": error_msg}), 500

# --- health check ---
@app.route('/health', methods=['GET'])
def health():
    return "السيرفر يعمل! ✅"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
