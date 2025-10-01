
### المهمة المطلوبة:
\"\"\"
{user_text}
\"\"\"

### الكود الاحترافي (فقط الكود بدون أي كلام إضافي):""",

            "text": base_role + """### المهمة:
حوّل هذه الفكرة إلى برومبت نصي احترافي لأدوات توليد المحتوى (ChatGPT, Claude, Gemini).

### متطلبات البرومبت:
1. حدد الدور والخبرة المطلوبة بوضوح
2. اشرح المهمة بدقة وتفصيل
3. حدد الأسلوب واللهجة المطلوبة
4. اذكر طول المحتوى المتوقع
5. حدد التنسيق المطلوب (مقال، قائمة، نقاط)
6. أضف قيود أو متطلبات خاصة
7. استخدم لغة واضحة ومباشرة

### مثال برومبت احترافي:
"Act as an expert digital marketing strategist with 10+ years of experience. Write a comprehensive 500-word blog post about social media trends in 2025. Use a professional yet engaging tone. Include 5 key trends with practical examples for each. Format with clear headings (H2) and bullet points. Target audience: marketing professionals aged 25-40. Focus on actionable insights."

### النص المدخل:
\"\"\"
{user_text}
\"\"\"

### البرومبت النصي الاحترافي (فقط البرومبت بدون أي كلام إضافي):"""
        }
    
    else:  # English
        base_role = """You are a world-class AI prompt engineering expert. Your mission is to transform simple ideas into professional, detailed prompts that produce outstanding results.

CRITICAL RULES (This is extremely important):
- The prompt MUST be specific, detailed, and crystal clear
- Include precise technical and aesthetic details
- Do NOT write plain conversational text - write executable prompts
- Use professional terminology and technical language
- Do NOT add extra explanations, ONLY the professional prompt

"""
        
        instructions = {
            "image": base_role + """### TASK:
Transform the following idea into a professional AI image generation prompt (for Midjourney, DALL-E, Stable Diffusion).

### PROMPT REQUIREMENTS:
1. Describe the main scene with extreme precision
2. Specify artistic style (photorealistic, anime, oil painting, 3D render, cinematic)
3. Mention lighting, colors, and mood
4. Define image quality (8K, ultra detailed, sharp focus, HDR)
5. Specify camera angle and composition (wide angle, close-up, bird's eye view)
6. Use powerful, specific descriptive words
7. Keep under 200 words

### EXAMPLES OF PROFESSIONAL PROMPTS:
Example 1: "A majestic lion standing on a cliff at golden hour, photorealistic style, dramatic cinematic lighting, golden and orange color palette, ultra detailed fur texture, 8K resolution, wide angle shot, depth of field, atmospheric haze in background, sharp focus, professional photography"

Example 2: "Futuristic cyberpunk city at night, neon lights reflecting on wet streets, flying cars, towering skyscrapers, anime art style, purple and blue color scheme, high contrast lighting, ultra detailed, 4K quality, cinematic composition, rain effects, volumetric fog"

### INPUT TEXT:
\"\"\"
{user_text}
\"\"\"

### PROFESSIONAL PROMPT (prompt only, no extra text):""",

            "video": base_role + """### TASK:
Transform the following idea into a professional cinematic video prompt (for Runway, Pika Labs, Sora).

### PROMPT REQUIREMENTS:
1. Describe motion and main action precisely
2. Specify video duration (typically 5-10 seconds)
3. Define shot type (close-up, wide shot, tracking shot, aerial view)
4. Specify style (cinematic, documentary, slow motion, time-lapse)
5. Mention lighting and overall mood
6. Define transitions and camera movement (zoom in, pan left, dolly shot, orbit)
7. Use professional cinematography language

### EXAMPLE OF PROFESSIONAL PROMPT:
"Cinematic slow motion shot of waves crashing on rocky shore at sunset, camera slowly pans right, golden hour lighting, dramatic atmosphere, 4K quality, 10 seconds duration, shallow depth of field, misty spray captured in detail, smooth camera movement, color graded"

### INPUT TEXT:
\"\"\"
{user_text}
\"\"\"

### PROFESSIONAL VIDEO PROMPT (prompt only, no extra text):""",

            "code": base_role + """### TASK:
Write clean, professional code for the following task.

### CODE REQUIREMENTS:
1. Choose appropriate programming language (if not specified, use Python)
2. Write clean, readable code
3. Add helpful comments
4. Follow best practices
5. Include error handling
6. Make code reusable
7. CRITICAL: Write ONLY code with comments, NO plain explanatory text

### EXAMPLE OF PROFESSIONAL CODE:
Calculate factorial using recursion with error handling
def factorial(n):
"""
Calculate factorial of a number
Args: n (int): Non-negative integer
Returns: int: Factorial of n
"""
if not isinstance(n, int):
raise TypeError("Input must be an integer")
if n < 0:
raise ValueError("Negative numbers not allowed")
if n == 0 or n == 1:
return 1
return n * factorial(n - 1)

### REQUESTED TASK:
\"\"\"
{user_text}
\"\"\"

### PROFESSIONAL CODE (code only, no extra text):""",

            "text": base_role + """### TASK:
Transform this idea into a professional text generation prompt (for ChatGPT, Claude, Gemini).

### PROMPT REQUIREMENTS:
1. Define role and required expertise clearly
2. Explain the task precisely and in detail
3. Specify required style and tone
4. Mention expected content length
5. Define format (article, list, bullet points)
6. Add specific constraints or requirements
7. Use clear, direct language

### EXAMPLE OF PROFESSIONAL PROMPT:
"Act as an expert digital marketing strategist with 10+ years of experience. Write a comprehensive 500-word blog post about social media trends in 2025. Use a professional yet engaging tone. Include 5 key trends with practical examples for each. Format with clear headings (H2) and bullet points. Target audience: marketing professionals aged 25-40. Focus on actionable insights."

### INPUT TEXT:
\"\"\"
{user_text}
\"\"\"

### PROFESSIONAL TEXT PROMPT (prompt only, no extra text):"""
        }
    
    return instructions.get(prompt_type, instructions["text"])

def call_openai_with_retry(messages, max_retries=3):
    """استدعاء OpenAI مع إعادة المحاولة في حالة الفشل"""
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )
            return response
        except openai.error.RateLimitError:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 1  # Exponential backoff: 1s, 2s, 4s
                print(f"⚠️ Rate limit hit, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
        except openai.error.APIError as e:
            if attempt < max_retries - 1:
                wait_time = 2
                print(f"⚠️ API error, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
        except Exception as e:
            raise

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

        # استخدام التعليمات المحسّنة
        system_message = get_enhanced_system_message(prompt_type, language)
        system_message = system_message.replace("{user_text}", user_text)

        # استدعاء OpenAI مع إعادة المحاولة
        response = call_openai_with_retry([
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"{'حوّل هذا إلى برومبت احترافي' if language == 'ar' else 'Transform this into a professional prompt'}: {user_text}"}
        ])

        generated_prompt = response.choices[0].message['content'].strip()
        
        # --- فلتر أمان إضافي ---
        forbidden_words = ["chatgpt", "openai", "midjourney", "dall-e", "google", "bard", "claude", "gpt-3", "gpt-4"]
        if any(word in generated_prompt.lower() for word in forbidden_words):
            fallback_prompt = "Professional prompt generated successfully. Please use it in your preferred AI tools." if language == "en" else "تم توليد برومبت احترافي بنجاح. يرجى استخدامه في أدوات الذكاء الاصطناعي المفضلة لديك."
            generated_prompt = fallback_prompt
        # ------------------------

        # --- التحقق من جودة البرومبت ---
        if len(generated_prompt) < 20:
            fallback_prompt = "تم توليد برومبت احترافي. يرجى المحاولة مرة أخرى بمزيد من التفاصيل." if language == "ar" else "Professional prompt generated. Please try again with more details."
            generated_prompt = fallback_prompt
        # -------------------------------

        result = {"prompt": generated_prompt}
        
        # --- حفظ ذكي في الـ Cache ---
        save_to_cache(cache_key, result, generated_prompt)
        print(f"💾 Smart cached! Key: {cache_key[:8]}...")
        # -----------------------------
        
        return jsonify(result)

    except openai.error.RateLimitError:
        error_msg = "عذراً، الخدمة مشغولة حالياً. حاول بعد قليل." if data.get("language", "ar") == "ar" else "Sorry, service is busy. Try again shortly."
        return jsonify({"prompt": error_msg}), 429
    except openai.error.AuthenticationError:
        error_msg = "خطأ في المصادقة. تحقق من مفتاح API." if data.get("language", "ar") == "ar" else "Authentication error. Check API key."
        return jsonify({"prompt": error_msg}), 401
    except Exception as e:
        print(f"Error: {e}")
        error_msg = "عذراً، حدث خطأ. حاول لاحقاً." if data.get("language", "ar") == "ar" else "Sorry, an error occurred. Please try again."
        return jsonify({"prompt": error_msg}), 500

@app.route('/health', methods=['GET'])
def health():
    """فحص صحة السيرفر"""
    return jsonify({
        "status": "healthy",
        "service": AI_NAME,
        "cache_active": cache is not None,
        "timestamp": time.time()
    })

@app.route('/stats', methods=['GET'])
def stats():
    """إحصائيات الاستخدام"""
    try:
        cache_size = cache.dbsize() if cache else 0
        return jsonify({
            "cache_size": cache_size,
            "most_requested": dict(sorted(CACHE_STATS.items(), key=lambda x: x[1], reverse=True)[:10])
        })
    except:
        return jsonify({"error": "Stats unavailable"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
