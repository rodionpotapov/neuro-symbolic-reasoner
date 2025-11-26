import os
import requests
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

from resolution_engine import LogicResolutionEngine

load_dotenv()
app = Flask(__name__)
CORS(app)

PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', '')
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

def formalize_task(task_text: str) -> dict:
    prompt = f"""Ты — эксперт по математической логике. Переведи текстовую задачу на естественном языке в язык логики предикатов с использованием кванторов (∀,∃), →,∨,∧,¬, как в учебниках по МЛиТА. Каждый вывод обособлен. Формулы не расписывай словами — только формальный синтаксис.
    
Пример:
Все люди смертны. Сократ — человек.
→
1. ∀x (Человек(x) → Смертен(x))
2. Человек(Сократ)

Задача:
{task_text}
Выведи JSON СТРОГО В ФОРМАТЕ:
{{
  "formulas": [
    "..."
  ],
  "goal": "..."
}}
"""
    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "sonar",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 512
        }
        resp = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=30)
        content = resp.json()['choices'][0]['message']['content']
        # Достаем чистый JSON (извлечение, даже если LLM проболтался)
        start = content.find('{')
        end = content.rfind('}')+1 if content.rfind('}') != -1 else len(content)
        data = json.loads(content[start:end])
        return data
    except Exception as e:
        return {"error": f"Ошибка формализации: {e}"}

def explain_proof_with_api(formulas, goal, steps, proven):
    prompt = f"""Ты — учитель по математической логике.
Объясни данное доказательство на русском для студента.

Формулы:
{formulas}
Цель: {goal}
Логи (шаги):
{"; ".join(steps[:15])}
Результат: {'Цель доказана ✓' if proven else 'Цель не доказана ✗'}

Объясни на 2-3 абзаца:
"""
    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "sonar",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 700
        }
        resp = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=30)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"[Ошибка объяснения]: {e}"

@app.route('/api/solve', methods=['POST'])
def solve():
    """Главный роут"""
    data = request.json
    if 'task' not in data:
        return jsonify({'error': 'Нет текста'}), 400
    user_task = data['task']
    
    # Модуль 1: LLM-формализатор
    form = formalize_task(user_task)
    if "error" in form:
        return jsonify({'error': form['error']}), 400
    formulas = form.get("formulas", [])
    goal = form.get("goal", "")
    if not (formulas and goal):
        return jsonify({'error': f"Пустые формулы: {formulas}, goal: {goal}"}), 400
    
    # Модуль 2: Символьные преобразования и резолюция
    engine = LogicResolutionEngine()
    resolution_result = engine.solve(formulas, goal)
    
    # Модуль 3: Объяснитель
    explanation = explain_proof_with_api(formulas, goal, resolution_result["steps"], resolution_result["proven"])
    
    return jsonify({
        "formulas": formulas,
        "goal": goal,
        "proof_steps": resolution_result["steps"],
        "proven": resolution_result["proven"],
        "explanation": explanation,
        "error": None
    })
    
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/examples')
def get_examples():
    return jsonify([
        {
            "title": "Сократ",
            "text": "Все люди смертны. Сократ — человек. Является ли Сократ смертным?"
        },
        {
            "title": "Птицы",
            "text": "Все птицы летают. Пингвин — птица. Летает ли пингвин?"
        },
        {
            "title": "Студенты",
            "text": "Все студенты учатся в университете. Иван — студент. Учится ли Иван в университете?"
        }
    ])

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "message": "Сервер работает"})

if __name__ == "__main__":
    app.run(debug=True, port=5009)
