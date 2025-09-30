# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import openai

# --- حل مشكلة proxies ---
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
# -------------------------

app = Flask(__name__)
CORS(app)

# احصل على مفتاح OpenAI من متغير البيئة
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/generate-prompt', methods=['POST'])
def generate_prompt():
    try:
        data = request.get_json()
        user_text = data.get("text", "").strip()
        prompt_type = data.get("type", "text")
        language = data.get("language", "ar")  # 'ar' للعربية، 'en' للإنجليزية

        if not user_text:
            return jsonify({"error": "الرجاء إدخال نص!" if language == "ar" else "Please enter text!"}), 400

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
            max_tokens=200,  # ← الحد الأقصى للتوكينات في المخرجات
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
