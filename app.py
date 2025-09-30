# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import openai
import re

# --- حل مشكلة proxies ---
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
# -------------------------

app = Flask(__name__)
CORS(app)

# احصل على مفتاح OpenAI من متغير البيئة
openai.api_key = os.getenv("OPENAI_API_KEY")

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
    
    # أنماط الأسئلة بالعربية (تشمل العامية)
    arabic_patterns = [
        # أسئلة الهوية الأساسية
        r"من أنت", r"مين أنت", r"شلونك", r"كيفك", r"وش اسمك", r"شسمك", r"اسمك إيش",
        r"هل أنت", r"أنت مين", r"تعرف نفسك", r"عرفنا بنفسك", r"شغلك إيش",
        # أسئلة الغرض والهدف
        r"ما هدفك", r"ما غرضك", r"لماذا تم إنشاؤك", r"لماذا صنعت", r"ليش خلقت",
        r"شغلك شنو", r"وظيفتك إيش", r"شتسوي", r"شتسوي بالضبط",
        # أسئلة المطور والمنشأ
        r"من صنعك", r"من مطورك", r"مين اللي صنعك", r"مين اللي خلقك", r"مين صاحبك",
        r"من شركتك", r"من شركتك الأم", r"من وراك", r"مين وراك",
        # أسئلة التقنية والعمل
        r"كيف تعمل", r"كيف تفكر", r"كيف تولد البرومبتس", r"شلون تشتغل",
        r"كيف تسوي البرومبتس", r"كيف تكتب", r"كيف تفهم", r"شلون تفهم",
        # أسئلة القدرات والحدود
        r"ما قدراتك", r"ما مميزاتك", r"شقدر أعمل", r"شيمكنك تسوي",
        r"ما حدودك", r"ما عيوبك", r"شينقصك", r"ما تقدر تسوي",
        # أسئلة الخصوصية والأمان
        r"هل تحمي خصوصيتي", r"هل تخزن بياناتي", r"هل تشارك معلوماتي",
        r"هل تذكرني", r"هل تعرفني", r"هل تسجل محادثاتنا", r"هل تحفظ اللي أكتبه",
        # أسئلة مباشرة عن الذكاء الاصطناعي
        r"هل أنت ذكاء اصطناعي", r"هل أنت روبوت", r"هل أنت برنامج",
        r"هل أنت بشري", r"هل عندك وعي", r"هل تحس", r"هل تفكر",
        # أسئلة قد تؤدي لذكر أسماء خارجية
        r"chatgpt", r"openai", r"midjourney", r"dall", r"google", r"bard", r"claude",
        r"أنت مثل", r"أنت نسخة من", r"أنت جي بي تي", r"gpt"
    ]
    
    # أنماط الأسئلة بالإنجليزية
    english_patterns = [
        # Identity questions
        r"who are you", r"what is your name", r"your name", r"are you", r"do you know yourself",
        r"introduce yourself", r"tell me about yourself", r"what do you do", r"what's your job",
        # Purpose questions
        r"what is your purpose", r"why were you created", r"why do you exist", r"what's your goal",
        # Creator questions
        r"who made you", r"who developed you", r"who created you", r"who owns you", r"who is behind you",
        # Technical questions
        r"how do you work", r"how do you think", r"how do you generate prompts", r"how are you built",
        # Capabilities questions
        r"what can you do", r"what are your capabilities", r"what are your features", r"what can i do with you",
        # Limitations questions
        r"what are your limitations", r"what are your weaknesses", r"what can't you do", r"what don't you know",
        # Privacy questions
        r"do you protect my privacy", r"do you store my data", r"do you share my information",
        r"do you remember me", r"do you know me", r"do you save our chats", r"do you keep what i write",
        # AI-related questions
        r"are you ai", r"are you a robot", r"are you a program", r"are you human", r"do you have consciousness",
        r"do you feel", r"do you think", r"chatgpt", r"openai", r"midjourney", r"dall", r"google", r"bard", r"claude",
        r"are you like", r"are you a version of", r"are you gpt", r"gpt"
    ]
    
    # التحقق من الأنماط
    for pattern in arabic_patterns + english_patterns:
        if re.search(pattern, text_lower):
            return True
    return False

def get_custom_response(text, language="ar"):
    """استرجاع الإجابة المخصصة بناءً على نوع السؤال"""
    text_lower = text.lower().strip()
    
    # تحديد نوع السؤال
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
        # إذا لم ينطبق أي نمط، استخدم الإجابة العامة
        return CUSTOM_RESPONSES[language]["identity"]

@app.route('/generate-prompt', methods=['POST'])
def generate_prompt():
    try:
        data = request.get_json()
        user_text = data.get("text", "").strip()
        prompt_type = data.get("type", "text")
        language = data.get("language", "ar")  # 'ar' للعربية، 'en' للإنجليزية

        if not user_text:
            return jsonify({"error": "الرجاء إدخال نص!" if language == "ar" else "Please enter text!"}), 400

        # --- فلتر شامل لجميع الأسئلة التي قد تكشف الهوية أو تذكر أسماء خارجية ---
        if is_identity_or_general_question(user_text):
            response_text = get_custom_response(user_text, language)
            return jsonify({"prompt": response_text})
        # --------------------------------------------------------------------

        # تعليمات حسب اللغة والنوع
        if language == "ar":
            instructions = {
                "image": "حوّل هذه الفكرة إلى برومبت احترافي لأدوات توليد الصور بالذكاء الاصطناعي باللغة العربية. اجعله مفصلاً واحترافياً، ولا يتجاوز 200 كلمة.",
                "code": "اكتب كوداً نظيفاً وفعالاً ومعلّقاً جيداً لهذه المهمة. حدّد لغة البرمجة إذا لم تُذكر.",
                "video": "أنشئ برومبت فيديو سينمائي مدته 10 ثوانٍ لأدوات توليد الفيديو بالذكاء الاصطناعي. كن محدداً بشأن المشهد والمزاج والأسلوب.",
                "text": "أعد كتابة هذا كبرومبت عالي الجودة لتوليد نصوص بالذكاء الاصطناعي."
            }
        else:  # اللغة الإنجليزية
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
        
        # --- فلتر أمان إضافي: منع أي ذكر لأسماء خارجية في النتائج ---
        forbidden_words = ["chatgpt", "openai", "midjourney", "dall", "google", "bard", "claude", "gpt"]
        if any(word in generated_prompt.lower() for word in forbidden_words):
            # إذا ظهر اسم خارجي، استخدم برومبت احتياطي
            fallback_prompt = "تم توليد برومبت احترافي بنجاح. يرجى استخدامه في أدوات الذكاء الاصطناعي المفضلة لديك."
            return jsonify({"prompt": fallback_prompt if language == "en" else "تم توليد برومبت احترافي بنجاح. يرجى استخدامه في أدوات الذكاء الاصطناعي المفضلة لديك."})
        # ----------------------------------------------------------------

        return jsonify({"prompt": generated_prompt})

    except Exception as e:
        error_msg = "عذراً، حدث خطأ. حاول لاحقاً." if data.get("language", "ar") == "ar" else "Sorry, an error occurred. Please try again."
        return jsonify({"prompt": error_msg}), 500

# نقطة تحقق بسيطة
@app.route('/health', methods=['GET'])
def health():
    return "السيرفر يعمل! ✅"

# تشغيل السيرفر على المنفذ الصحيح
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
