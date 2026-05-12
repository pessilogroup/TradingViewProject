import asyncio
import os
import sys
from pathlib import Path

# Add current dir to path to allow import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from vision import analyze_chart_vision

async def run_tests():
    # Use a dummy image from the project, or create one
    image_path = Path("test_image.png")
    
    # Create a dummy image if it doesn't exist
    if not image_path.exists():
        from PIL import Image
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save(image_path)
        print(f"Created dummy image at {image_path}")

    symbol = "TESTUSDT"
    scan_result = {"price": 100, "trend_template_score": 8, "vcp_detected": True}
    
    # Enable Gemini Testing
    # Ensure GEMINI_API_KEY is available in environment
    print("\n--- Testing Gemini ---")
    config.AI_PROVIDER = "gemini"
    res_gemini = await analyze_chart_vision(image_path, symbol, scan_result)
    print(f"Gemini Result: Confidence={res_gemini.get('confidence')}, Patterns={res_gemini.get('patterns')}, Verdict={res_gemini.get('verdict')}")
    if res_gemini.get('error'):
        print(f"Gemini Error: {res_gemini['error']}")

    print("\n--- Testing Anthropic ---")
    config.AI_PROVIDER = "anthropic"
    res_anthropic = await analyze_chart_vision(image_path, symbol, scan_result)
    print(f"Anthropic Result: Confidence={res_anthropic.get('confidence')}, Patterns={res_anthropic.get('patterns')}, Verdict={res_anthropic.get('verdict')}")
    if res_anthropic.get('error'):
        print(f"Anthropic Error: {res_anthropic['error']}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
    asyncio.run(run_tests())
