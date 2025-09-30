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
        "identity": f"أنا {AI_NAME}، نموذج ذكاء اصطناعي مصمم خصيصاً لتوليد برومبتات احترافية لأدوات الذكاء الاصطناعي مثل Midjourney وDALL·E وChatGPT. لا أملك هوية شخصية، بل أنا أداة لإلهامك وإنتاج أفكار مذهلة!",
        "purpose": f"وظيفتي هي تحويل أفكارك البسيطة إلى برومبتات دقيقة ومهنية يمكن استخدامها مباشرة في أدوات الذكاء الاصطناعي. فقط اكتب فكرتك، وأنا أحوّلها إلى أمر احترافي جاهز للتنفيذ.",
        "creator": "تم تصميمي بواسطة مطور عربي مهتم بتقنيات الذكاء الاصطناعي، بهدف تسهيل استخدام أدوات الذكاء الاصطناعي للمستخدمين العرب والعالميين.",
        "how_work": "أعمل عن طريق تحليل فكرتك، ثم صياغتها بلغة دقيقة تفهمها أدوات الذكاء الاصطناعي، مع إضافة التفاصيل الفنية والفنية التي تجعل النتائج أكثر دقة وإبداعاً.",
        "capabilities": "يمكنني توليد برومبتات للكتابة، البرمجة، الصور، والفيديوهات. كما أستطيع تحسين أي برومبت موجود لجعله أكثر احترافية وفعالية.",
        "limitations": "أنا لا أملك ذكاءً عاطفياً أو قدرة على التفاعل كإنسان، بل أنا أداة تقنية مبنية على نماذج لغوية. لا أستطيع تنفيذ الأوامر أو تخزين المعلومات الشخصية.",
        "privacy": "لا أخزن أي من مدخلاتك أو طلباتك. كل طلب يتم معالجته بشكل آمن، ولا يتم مشاركته مع أي طرف ثالث."
    },
    "en": {
        "identity": f"I am {AI_NAME}, an AI model specifically designed to generate professional prompts for AI tools like Midjourney, DALL·E, and ChatGPT. I don't have a personal identity — I'm your creative assistant for AI content generation!",
        "purpose": f"My purpose is to turn your simple ideas into precise, professional prompts ready to be used in AI tools. Just describe your idea, and I'll craft the perfect prompt for you.",
        "creator": "I was developed by an Arabic-speaking AI enthusiast aiming to make AI tools more accessible to Arabic and global users.",
        "how_work": "I analyze your idea, then rephrase it using technical and artistic details that AI tools understand best — ensuring high-quality, creative results every time.",
        "capabilities": "I can generate prompts for text, code, images, and videos. I can also enhance existing prompts to make them more effective and professional.",
        "limitations": "I don't have emotional intelligence or human-like awareness. I'm a technical tool built on language models — I can't execute commands or store personal data.",
        "privacy": "I don't store your inputs or requests. All data is processed securely and never shared with third parties."
    }
}

def is_identity_question(text):
    """تحقق مما إذا كان النص يحتوي على أسئلة هوية أو معلومات أساسية"""
    text_lower = text.lower().strip()
    
    # أنماط الأسئلة بالعربية
    arabic_patterns = [
        r"من أنت", r"ما اسمك", r"ما هو اسمك", r"هل أنت", r"من تكون", r"هل تعرف نفسك",
        r"ما هدفك", r"ما غرضك", r"لماذا تم إنشاؤك", r"من صنعك", r"من مطورك", r"من الذي صنعك",
        r"كيف تعمل", r"كيف تعمل؟", r"كيف تفكر", r"كيف تولد البرومبتس", r"ما قدراتك", r"ما مميزاتك",
        r"ما حدودك", r"ما عيوبك", r"هل تحمي خصوصيتي", r"هل تخزن بياناتي", r"هل تشارك معلوماتي"
    ]
    
    # أنماط الأسئلة بالإنجليزية
    english_patterns = [
        r"who are you", r"what is your name", r"your name", r"are you", r"do you know yourself",
        r"what is your purpose", r"why were you created", r"who made you", r"who developed you",
        r"how do you work", r"how do you think", r"how do you generate prompts", r"what can you do",
        r"what are your capabilities", r"what are your limitations", r"what are your weaknesses",
        r"do you protect my privacy", r"do you store my data", r"do you share my information"
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
    if re.search(r"(من أنت|who are you|ما اسمك|your name)", text_lower):
        return CUSTOM_RESPONSES[language]["identity"]
    elif re.search(r"(ما هدفك|what is your purpose|لماذا تم إنشاؤك|why were you created)", text_lower):
        return CUSTOM_RESPONSES[language]["purpose"]
    elif re.search(r"(من صنعك|who made you|من مطورك|who developed you)", text_lower):
        return CUSTOM_RESPONSES[language]["creator"]
    elif re.search(r"(كيف تعمل|how do you work|كيف تفكر|how do you think)", text_lower):
        return CUSTOM_RESPONSES[language]["how_work"]
    elif re.search(r"(ما قدراتك|what can you do|ما مميزاتك|what are your capabilities)", text_lower):
        return CUSTOM_RESPONSES[language]["capabilities"]
    elif re.search(r"(ما حدودك|what are your limitations|ما عيوبك|what are your weaknesses)", text_lower):
        return CUSTOM_RESPONSES[language]["limitations"]
    elif re.search(r"(هل تحمي خصوصيتي|do you protect my privacy|هل تخزن بياناتي|do you store my data)", text_lower):
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

        # --- فلتر الأسئلة الشخصية ---
        if is_identity_question(user_text):
            response_text = get_custom_response(user_text, language)
            return jsonify({"prompt": response_text})
        # ------------------------------

        # تعليمات حسب اللغة والنوع
        if language == "ar":
            instructions = {
                "image": "حوّل هذه الفكرة إلى برومبت احترافي لـ Midjourney أو DALL·E باللغة العربية. اجعله مفصلاً واحترافياً، ولا يتجاوز 200 كلمة.",
                "code": "اكتب كوداً نظيفاً وفعالاً ومعلّقاً جيداً لهذه المهمة. حدّد لغة البرمجة إذا لم تُذكر.",
                "video": "أنشئ برومبت فيديو سينمائي مدته 10 ثوانٍ لأدوات الذكاء الاصطناعي مثل Runway أو Pika. كن محدداً بشأن المشهد والمزاج والأسلوب.",
                "text": "أعد كتابة هذا كبرومبت عالي الجودة لتوليد نصوص بالذكاء الاصطناعي مثل ChatGPT."
            }
        else:  # اللغة الإنجليزية
            instructions = {
                "image": "Convert this idea into a detailed, professional Midjourney or DALL·E prompt in English. Keep it under 200 words.",
                "code": "Generate clean, efficient, and well-commented code for this task. Specify the programming language if not mentioned.",
                "video": "Create a cinematic, 10-second video prompt for AI video tools like Runway or Pika. Be specific about scene, mood, and style.",
                "text": "Rewrite this as a high-quality, engaging AI text generation prompt for ChatGPT or similar."
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
