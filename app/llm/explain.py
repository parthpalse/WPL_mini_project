"""AI explanation layer — calls local Ollama to explain engine results.

The LLM never computes numbers — it only explains pre-computed results.
"""

import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"  # or mistral

def explain_plan(engine_output: dict) -> str:
    """Generate a plain-language explanation of the financial plan.
    
    Args:
        engine_output: Dictionary containing computed financial figures.
    """
    prompt = f"""You are a helpful, encouraging financial assistant.
Explain the following pre-calculated financial plan to the user in simple terms.
Do NOT invent any new numbers. Do NOT do any math. Only explain what these numbers mean.

DATA:
- Monthly Surplus Available to Invest: ₹{engine_output.get('monthly_surplus', 0)}
- Safe Strategy Allocation: {json.dumps(engine_output.get('safe', {}))}
- Balanced Strategy Allocation: {json.dumps(engine_output.get('balanced', {}))}
- Growth Strategy Allocation: {json.dumps(engine_output.get('growth', {}))}

Provide a brief (max 3 paragraphs) summary of why diversifying across these products is beneficial based on their risk and liquidity. Keep it positive and encouraging.
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get('response', 'Explanation generated successfully.')
    except requests.exceptions.RequestException as e:
        return f"AI explanation is currently unavailable (Ollama might not be running). Error: {str(e)}"

