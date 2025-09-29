# app.py
from flask import Flask, request, jsonify
from openai import OpenAI
import os

app = Flask(__name__)

# احصل على مفتاح OpenAI من متغير البيئة (آمن)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route('/generate-prompt', methods=['POST'])
def generate_prompt():
    try:
        data = request.get_json()
        user_text = data.get("text", "").strip()
        prompt_type = data.get("type", "text")

        if not user_text:
            return jsonify({"error": "الرجاء إدخال نص!"}), 400

        # تعليمات حسب نوع البرومبت
        instructions = {
            "image": "Convert this idea into a detailed, professional Midjourney or DALL·E prompt in English. Keep it under 80 words.",
            "code": "Generate clean, efficient, and well-commented code for this task. Specify the programming language if not mentioned.",
            "video": "Create a cinematic, 10-second video prompt for AI video tools like Runway or Pika. Be specific about scene, mood, and style.",
            "text": "Rewrite this as a high-quality, engaging AI text generation prompt for ChatGPT or similar."
        }

        system_message = instructions.get(prompt_type, instructions["text"])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_text}
            ],
            max_tokens=100,
            temperature=0.7
        )

        generated_prompt = response.choices[0].message.content.strip()
        return jsonify({"prompt": generated_prompt})

    except Exception as e:
        return jsonify({"prompt": "عذراً، حدث خطأ. حاول لاحقاً."}), 500

# نقطة تحقق بسيطة
@app.route('/health', methods=['GET'])
def health():
    return "السيرفر يعمل! ✅"
