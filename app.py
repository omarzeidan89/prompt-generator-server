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

# احصل على مفتاح OpenAI من متغير البيئة
openai.api_key = os.getenv("OPENAI_API_KEY")

# إعداد Redis Cache
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    cache = redis.from_url(redis_url)
    cache.ping()  # تحقق من الاتصال
    print("✅ Redis connected successfully!")
except Exception as e:
    cache = None
    print(f"⚠️ Redis not available: {e}")

# إعدادات الـ Cache الذكي
MAX_CACHE_SIZE = 1000  # الحد الأقصى لعدد العناصر في الذاكرة
CACHE_STATS = defaultdict(int)  # تتبع عدد مرات طلب كل برومبت

# اسم النموذج الذي تريده
AI_NAME = "AI Prompts Generator"

# الإجابات المخصصة حسب اللغة
CUSTOM_RESPONSES = {
    "ar": {
        "identity": f"أنا {AI_NAME}، نموذج ذكاء اصطناعي مصمم خصيصاً لتوليد برومبتات احترافية لأدوات الذكاء الاصطناعي. لا أملك هوية شخصية، بل أنا أداة لإلهامك وإنتاج أفكار مذهلة!",
        "purpose": f"وظيفتي هي تحويل أفكارك البسيطة إلى برومبتات دقيقة ومهنية يمكن استخدامها مباشرة في أدوات الذكاء الاصطناعي. فقط اكتب فكرتك، وأنا أحوّلها إلى أمر احترافي جاهز للتنفيذ.",
        "creator": "تم تصميمي بواسطة مطور عربي مهتم بتقنيات الذكاء الاصطناعي، بهدف تسهيل استخدام أدوات الذكاء الاصطناعي للمستخدمين العرب والعالميين.",
        "how_work": "أعمل عن طريق تحليل فكرتك، ثم صياغتها بلغة دقيقة تفهمها أدوات الذكاء الاصطناعي، مع إضاع التفاصيل الفنية والفنية التي تجعل النتائج أكثر دقة وإبداعاً.",
        "capabilities": "يمكنني توليد برومبتات للكتابة، البرمجة، الصور، والفيديوهات. كما أستطيع تحسين أي برومبت موجود لجعله أكثر احترافية وفعالية.",
        "limitations": "أنا لا أملك ذكاءً عاطفياً أو قدرة على التفاعل كإنسان، بل أنا أداة تقنية مبنية على نماذج لغوية. لا أستطيع تنفيذ الأوامر أو تخزين المعلومات الشخصية.",
        "privacy": "لا أخزن أي من مدخلاتك أو طلباتك. كل طلب يتم معالجته بشكل آمن، ولا يتم مشاركته مع أي طرف ثالث."
    },
    "en": {
        "identity": f"I am {AI_NAME}, an AI model specifically designed to generate professional prompts for AI tools. I don't have a personal identity — I'm your creative assistant for AI content generation!",
        "purpose": f"My purpose is to turn your simple ideas into precise, professional prompts ready to be used in AI tools. Just describe your idea, and I'll craft the perfect prompt for you.",
        "creator": "I was developed by an Arabic-speaking AI enthusiast aiming to make AI tools more accessible to Arabic and global users.",
        "how_work": "I analyze your idea, then rephrase it using technical and artistic details that AI tools understand best — ensuring high-quality, creative results every time.",
        "capabilities": "I can generate prompts for text, code, images, and videos. I can also enhance existing prompts to make them more effective and professional.",
        "limitations": "I don't have emotional intelligence or human-like awareness. I'm a technical tool built on language models — I can't execute commands or store personal data.",
        "privacy": "I don't store your inputs or requests. All data is processed securely and never shared with third parties."
    }
}

def is_identity_or_general_question(text):
    """تحقق مما إذا كان النص يحتوي على أسئلة هوية أو أسئلة عامة قد تكشف عن الهوية"""
    text_lower = text.lower().strip()
    
    arabic_patterns = [
        r"من أنت", r"مين أنت", r"شلونك", r"كيفك", r"وش اسمك", r"شسمك", r"اسمك إيش",
        r"هل أنت", r"أنت مين", r"تعرف نفسك", r"عرفنا بنفسك", r"شغلك إيش",
        r"ما هدفك", r"ما غرضك", r"لماذا تم إنشاؤك", r"لماذا صنعت", r"ليش خلقت",
        r"شغلك شنو", r"وظيفتك إيش", r"شتسوي", r"شتسوي بالضبط",
        r"من صنعك", r"من مطورك", r"مين اللي صنعك", r"مين اللي خلقك", r"مين صاحبك",
        r"من شركتك", r"من شركتك الأم", r"من وراك", r"مين وراك",
        r"كيف تعمل", r"كيف تفكر", r"كيف تولد البرومبتس", r"شلون تشتغل",
        r"كيف تسوي البرومبتس", r"كيف تكتب", r"كيف تفهم", r"شلون تفهم",
        r"ما قدراتك", r"ما مميزاتك", r"شقدر أعمل", r"شيمكنك تسوي",
        r"ما حدودك", r"ما عيوبك", r"شينقصك", r"ما تقدر تسوي",
        r"هل تحمي خصوصيتي", r"هل تخزن بياناتي", r"هل تشارك معلوماتي",
        r"هل تذكرني", r"هل تعرفني", r"هل تسجل محادثاتنا", r"هل تحفظ اللي أكتبه",
        r"هل أنت ذكاء اصطناعي", r"هل أنت روبوت", r"هل أنت برنامج",
        r"هل أنت بشري", r"هل عندك وعي", r"هل تحس", r"هل تفكر",
        r"chatgpt", r"openai", r"midjourney", r"dall", r"google", r"bard", r"claude",
        r"أنت مثل", r"أنت نسخة من", r"أنت جي بي تي", r"gpt"
    ]
    
    english_patterns = [
        r"who are you", r"what is your name", r"your name", r"are you", r"do you know yourself",
        r"introduce yourself", r"tell me about yourself", r"what do you do", r"what's your job",
        r"what is your purpose", r"why were you created", r"why do you exist", r"what's your goal",
        r"who made you", r"who developed you", r"who created you", r"who owns you", r"who is behind you",
        r"how do you work", r"how do you think", r"how do you generate prompts", r"how are you built",
        r"what can you do", r"what are your capabilities", r"what are your features", r"what can i do with you",
        r"what are your limitations", r"what are your weaknesses", r"what can't you do", r"what don't you know",
        r"do you protect my privacy", r"do you store my data", r"do you share my information",
        r"do you remember me", r"do you know me", r"do you save our chats", r"do you keep what i write",
        r"are you ai", r"are you a robot", r"are you a program", r"are you human", r"do you have consciousness",
        r"do you feel", r"do you think", r"chatgpt", r"openai", r"midjourney", r"dall", r"google", r"bard", r"claude",
        r"are you like", r"are you a version of", r"are you gpt", r"gpt"
    ]
    
    for pattern in arabic_patterns + english_patterns:
        if re.search(pattern, text_lower):
            return True
    return False

def get_custom_response(text, language="ar"):
    """استرجاع الإجابة المخصصة بناءً على نوع السؤال"""
    text_lower = text.lower().strip()
    
    if re.search(r"(من أنت|who are you|ما اسمك|your name|مين أنت|وش اسمك|شسمك)", text_lower):
        return CUSTOM_RESPONSES[language]["identity"]
    elif re.search(r"(ما هدفك|what is your purpose|لماذا تم إنشاؤك|why were you created|شغلك إيش|what do you do)", text_lower):
        return CUSTOM_RESPONSES[language]["purpose"]
    elif re.search(r"(من صنعك|who made you|من مطورك|who developed you|مين اللي صنعك|who owns you)", text_lower):
        return CUSTOM_RESPONSES[language]["creator"]
    elif re.search(r"(كيف تعمل|how do you work|كيف تفكر|how do you think|شلون تشتغل|how are you built)", text_lower):
        return CUSTOM_RESPONSES[language]["how_work"]
    elif re.search(r"(ما قدراتك|what can you do|ما مميزاتك|what are your capabilities|شيمكنك تسوي|what can i do)", text_lower):
        return CUSTOM_RESPONSES[language]["capabilities"]
    elif re.search(r"(ما حدودك|what are your limitations|ما عيوبك|what are your weaknesses|شينقصك|what can't you do)", text_lower):
        return CUSTOM_RESPONSES[language]["limitations"]
    elif re.search(r"(هل تحمي خصوصيتي|do you protect my privacy|هل تخزن بياناتي|do you store my data|هل تحفظ اللي أكتبه|do you keep what i write)", text_lower):
        return CUSTOM_RESPONSES[language]["privacy"]
    else:
        return CUSTOM_RESPONSES[language]["identity"]

def calculate_smart_expiry(prompt_text, request_count=1):
    """حساب مدة التخزين الذكية بناءً على التعقيد والتكرار"""
    prompt_length = len(prompt_text)
    length_factor = min(prompt_length / 100, 3)
    repeat_factor = min(request_count / 5, 4)
    base_time = 86400  # 24 ساعة
    smart_expiry = int(base_time * length_factor * repeat_factor)
    return min(smart_expiry, 2592000)  # لا تتجاوز 30 يوماً

def generate_cache_key(text, prompt_type, language):
    """إنشاء مفتاح فريد للـ Cache"""
    key_data = f"{text}|{prompt_type}|{language}"
    return hashlib.md5(key_data.encode()).hexdigest()

def get_from_cache(key):
    """استرجاع من الـ Cache مع تتبع الإحصائيات"""
    if cache is None:
        return None
    try:
        CACHE_STATS[key] += 1
        cached_data = cache.hgetall(f"prompt:{key}")
        if cached_data and b'prompt' in cached_data:
            prompt_text = cached_data[b'prompt'].decode('utf-8')
            return {"prompt": prompt_text}
    except Exception as e:
        print(f"Cache get error: {e}")
    return None

def save_to_cache(key, value, prompt_text):
    """حفظ في الـ Cache مع إدارة ذكية للذاكرة"""
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

@app.route('/generate-prompt', methods=['POST'])
def generate_prompt():
    try:
        data = request.get_json()
        user_text = data.get("text", "").strip()
        prompt_type = data.get("type", "text")
        language = data.get("language", "ar")

        if not user_text:
            return jsonify({"error": "الرجاء إدخال نص!" if language == "ar" else "Please enter text!"}), 400

        # --- فلتر شامل لجميع الأسئلة التي قد تكشف الهوية ---
        if is_identity_or_general_question(user_text):
            response_text = get_custom_response(user_text, language)
            return jsonify({"prompt": response_text})
        # ----------------------------------------------------

        # --- التحقق من الـ Cache أولاً ---
        cache_key = generate_cache_key(user_text, prompt_type, language)
        cached_result = get_from_cache(cache_key)
        if cached_result:
            print("✅ Cache hit!")
            return jsonify(cached_result)
        # --------------------------------

        # تعليمات حسب اللغة والنوع
        if language == "ar":
            instructions = {
                "image": "حوّل هذه الفكرة إلى برومبت احترافي لأدوات توليد الصور بالذكاء الاصطناعي باللغة العربية. اجعله مفصلاً واحترافياً، ولا يتجاوز 200 كلمة.",
                "code": "اكتب كوداً نظيفاً وفعالاً ومعلّقاً جيداً لهذه المهمة. حدّد لغة البرمجة إذا لم تُذكر.",
                "video": "أنشئ برومبت فيديو سينمائي مدته 10 ثوانٍ لأدوات توليد الفيديو بالذكاء الاصطناعي. كن محدداً بشأن المشهد والمزاج والأسلوب.",
                "text": "أعد كتابة هذا كبرومبت عالي الجودة لتوليد نصوص بالذكاء الاصطناعي."
            }
        else:
            instructions = {
                "image": "Convert this idea into a detailed, professional AI image generation prompt in English. Keep it under 200 words.",
                "code": "Generate clean, efficient, and well-commented code for this task. Specify the programming language if not mentioned.",
                "video": "Create a cinematic, 10-second AI video generation prompt. Be specific about scene, mood, and style.",
                "text": "Rewrite this as a high-quality, engaging AI text generation prompt."
            }

        system_message = instructions.get(prompt_type, instructions["text"])

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_text}
            ],
            max_tokens=200,
            temperature=0.7
        )

        generated_prompt = response.choices[0].message['content'].strip()
        
        # --- فلتر أمان إضافي ---
        forbidden_words = ["chatgpt", "openai", "midjourney", "dall", "google", "bard", "claude", "gpt"]
        if any(word in generated_prompt.lower() for word in forbidden_words):
            fallback_prompt = "تم توليد برومبت احترافي بنجاح. يرجى استخدامه في أدوات الذكاء الاصطناعي المفضلة لديك."
            generated_prompt = fallback_prompt if language == "en" else "تم توليد برومبت احترافي بنجاح. يرجى استخدامه في أدوات الذكاء الاصطناعي المفضلة لديك."
        # ------------------------

        result = {"prompt": generated_prompt}
        
        # --- حفظ ذكي في الـ Cache ---
        save_to_cache(cache_key, result, generated_prompt)
        print(f"💾 Smart cached! Key: {cache_key[:8]}...")
        # -----------------------------
        
        return jsonify(result)

    except Exception as e:
        error_msg = "عذراً، حدث خطأ. حاول لاحقاً." if data.get("language", "ar") == "ar" else "Sorry, an error occurred. Please try again."
        return jsonify({"prompt": error_msg}), 500

@app.route('/health', methods=['GET'])
def health():
    return "السيرفر يعمل! ✅"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
