from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import openai
import os

# إعداد Flask
app = Flask(__name__)
CORS(app)

# إعداد الـ Rate Limiting (تحديد عدد الطلبات)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20 per minute"]  # 20 طلب بالدقيقة لكل IP
)

# مفتاح OpenAI من متغير البيئة
openai.api_key = os.getenv("OPENAI_API_KEY")

# -------- وظائف المساعدة -------- #

def detect_intent(user_input):
    """استخدام GPT لاكتشاف نية المستخدم (نص / صورة / فيديو / كود)"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "حلل النص وحدد إذا كان المقصود: نص، صورة، فيديو، أو كود. جاوب بكلمة واحدة فقط بدون شرح."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=5,
            temperature=0
        )
        intent = response.choices[0].message["content"].strip()
        return intent if intent in ["نص", "صورة", "فيديو", "كود"] else "نص"
    except Exception:
        return "نص"

def generate_prompt(user_input, intent):
    """توليد برومبت احترافي بناءً على النوع"""
    if intent == "صورة":
        system_instruction = "حوّل النص إلى برومبت احترافي لتوليد صورة بالذكاء الاصطناعي (مثل DALL·E أو Stable Diffusion)."
    elif intent == "فيديو":
        system_instruction = "حوّل النص إلى برومبت احترافي لتوليد فيديو قصير بالذكاء الاصطناعي."
    elif intent == "كود":
        system_instruction = "حوّل النص إلى برومبت احترافي لتوليد كود برمجي نظيف ومفهوم."
    else:
        system_instruction = "حوّل النص إلى برومبت نصي احترافي يمكن استخدامه مع GPT."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_input}
            ],
            max_tokens=400,
            temperature=0.7
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        return f"Error: {str(e)}"

# -------- نقاط النهاية API -------- #

@app.route("/generate", methods=["POST"])
@limiter.limit("10 per minute")  # تحديد 10 طلبات بالدقيقة لكل مستخدم
def generate():
    """واجهة API لتوليد البرومبت"""
    data = request.json
    user_input = data.get("prompt", "").strip()
    selected_type = data.get("type", "").strip()

    if not user_input:
        return jsonify({"error": "الرجاء إدخال نص صحيح"}), 400

    # إذا المستخدم ما حدد النوع → نخلي GPT يحدد
    if not selected_type:
        selected_type = detect_intent(user_input)

    prompt = generate_prompt(user_input, selected_type)

    return jsonify({
        "intent": selected_type,
        "prompt": prompt
    })

# -------- تشغيل السيرفر -------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
