#!/usr/bin/env python3
"""
🌙 LUNA Image Generator — OpenRouter FLUX.2 Klein 4B
Genera imágenes vía OpenRouter, las descarga y las prepara para el pipeline.

Uso:
  python3 luna-gen.py --prompt "texto" --output ruta --width 1200 --height 630
  
  python3 luna-gen.py --prompt "texto" --output ruta --style polaris-dfy
  python3 luna-gen.py --prompt "texto" --output ruta --style backbone
  python3 luna-gen.py --prompt "texto" --output ruta --style visionnorth
  python3 luna-gen.py --prompt "texto" --output ruta --style padim
"""

import os, sys, json, base64, argparse, time
import requests
from pathlib import Path
from PIL import Image

# ─── Config ────────────────────────────────────────────────
def _get_api_key():
    """Lee OPENROUTER_API_KEY desde .env del profile"""
    env_paths = [
        "/home/polaris/.hermes/profiles/omegabridge/.env",
        "/home/polaris/.hermes/.env",
        "/home/polaris/.env",
    ]
    for p in env_paths:
        try:
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except: pass
    return os.environ.get("OPENROUTER_API_KEY", "")

OPENROUTER_API_KEY = _get_api_key()
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
MODEL = "black-forest-labs/flux.2-klein-4b"
SITE_URL = "https://polarisgrow.com"
SITE_NAME = "Polaris by VisionNorth"

# ─── Estilos predefinidos ─────────────────────────────────
STYLES = {
    "polaris-dfy": {
        "colors": "dark background (#121215), emerald green accent (#1EDB7F), warm tones",
        "mood": "premium agency, warm, professional, aspirational",
        "style": "commercial photography, dark elegant, editorial quality",
        "negative": "text, logo, people, cartoon, low quality, blurry",
    },
    "backbone": {
        "colors": "dark navy (#0a0c14), blue accent (#0061FE), clean white",
        "mood": "technical, precise, data-driven, enterprise",
        "style": "tech documentation, clean minimal, data visualization aesthetic",
        "negative": "text, people, real estate, agency style, bright colors",
    },
    "visionnorth": {
        "colors": "dark (#0c0e12), emerald green (#0bf47e), teal (#00b4d8)",
        "mood": "modern, accessible, SaaS, platform feel",
        "style": "modern SaaS marketing, clean UI, flat design elements",
        "negative": "text, people, cluttered, low quality",
    },
    "padim": {
        "colors": "dark neutral (#161c26), blue accent (#4a8fe7), white",
        "mood": "open source, academic, community, protocol",
        "style": "open source documentation, clean technical, node network visuals",
        "negative": "text, commercial, pricing, real estate photos",
    },
}

def generate_image(prompt, output_path, width=1024, height=1024, style=None, num_images=1):
    """Generate image via OpenRouter FLUX.2 Klein 4B"""
    
    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY no configurada")
        return False
    
    # Apply style if specified
    if style and style in STYLES:
        s = STYLES[style]
        full_prompt = f"{prompt}. Style: {s['style']}. Mood: {s['mood']}. Colors: {s['colors']}. NO text, NO logos, NO people."
        negative = s['negative']
    else:
        full_prompt = prompt
        negative = ""
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
    }
    
    payload = {
        "model": MODEL,
        "prompt": full_prompt,
        "n": num_images,
        "size": f"{width}x{height}",
        "response_format": "b64_json",
    }
    
    if negative:
        payload["negative_prompt"] = negative
    
    try:
        print(f"  🎨 Generando con {MODEL}...")
        print(f"  📐 {width}x{height} | estilo: {style or 'personalizado'}")
        
        resp = requests.post(
            f"{OPENROUTER_BASE}/images/generations",
            headers=headers,
            json=payload,
            timeout=120,
        )
        
        if resp.status_code != 200:
            print(f"  ❌ Error {resp.status_code}: {resp.text[:200]}")
            # Try chat completions format as fallback
            return _try_chat_format(full_prompt, output_path, width, height)
        
        data = resp.json()
        images = []
        for i, img_data in enumerate(data.get("data", [])):
            b64 = img_data.get("b64_json")
            if b64:
                path = _save_image(b64, output_path, i)
                if path:
                    images.append(path)
        
        if images:
            print(f"  ✅ {len(images)} imagen(es) generada(s): {images[0]}")
            return True
        
        # If no b64_json, try URL
        for img_data in data.get("data", []):
            url = img_data.get("url")
            if url:
                path = _download_url(url, output_path)
                if path:
                    print(f"  ✅ Imagen descargada: {path}")
                    return True
        
        print(f"  ⚠️ Formato inesperado: {json.dumps(data, indent=2)[:300]}")
        return False
        
    except Exception as e:
        print(f"  ❌ Excepción: {e}")
        return False


def _try_chat_format(prompt, output_path, width, height):
    """Fallback: intentar con chat completions endpoint"""
    print("  🔄 Intentando con chat completions...")
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": f"Generate an image: {prompt}"},
                {"type": "image_size", "image_size": {"width": width, "height": height}}
            ]}
        ],
    }
    
    try:
        resp = requests.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        
        if resp.status_code != 200:
            print(f"  ❌ Chat falló: {resp.status_code}")
            return False
        
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if content and isinstance(content, list):
            for item in content:
                if item.get("type") == "image_url":
                    url = item["image_url"]["url"]
                    path = _download_url(url, output_path)
                    if path:
                        print(f"  ✅ Imagen via chat: {path}")
                        return True
                elif item.get("type") == "text":
                    b64 = item.get("b64_json")
                    if b64:
                        path = _save_image(b64, output_path, 0)
                        if path:
                            return True
        
        print(f"  ⚠️ Chat response: {json.dumps(data, indent=2)[:300]}")
        return False
        
    except Exception as e:
        print(f"  ❌ Chat exception: {e}")
        return False


def _save_image(b64_data, output_path, index=0):
    """Save base64 image to file"""
    try:
        if "," in b64_data:
            b64_data = b64_data.split(",")[1]
        
        img_bytes = base64.b64decode(b64_data)
        path = Path(output_path)
        
        if path.suffix == "":
            path = path.parent / f"{path.stem}_{index}.png"
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(img_bytes)
        
        # Convert to WebP
        webp_path = path.with_suffix(".webp")
        img = Image.open(path)
        img.save(str(webp_path), "WEBP", quality=85)
        
        return str(path)
    except Exception as e:
        print(f"  ❌ Error guardando imagen: {e}")
        return None


def _download_url(url, output_path):
    """Download image from URL"""
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            return None
        
        path = Path(output_path)
        if path.suffix == "":
            path = path.with_suffix(".png")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        
        # Convert to WebP
        webp_path = path.with_suffix(".webp")
        img = Image.open(path)
        img.save(str(webp_path), "WEBP", quality=85)
        
        return str(path)
    except Exception as e:
        print(f"  ❌ Error descargando: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="🌙 LUNA Image Generator")
    parser.add_argument("--prompt", "-p", required=True, help="Prompt de la imagen")
    parser.add_argument("--output", "-o", default="./luna-output/image.png", help="Ruta de salida")
    parser.add_argument("--width", "-w", type=int, default=1024, help="Ancho")
    parser.add_argument("--height", "-ht", type=int, default=1024, help="Alto")
    parser.add_argument("--style", "-s", choices=list(STYLES.keys()) + [None], default=None, help="Estilo predefinido")
    parser.add_argument("--num", "-n", type=int, default=1, help="Número de imágenes")
    
    args = parser.parse_args()
    
    print(f"\n🌙 LUNA Image Generator")
    print(f"{'='*50}")
    
    success = generate_image(
        prompt=args.prompt,
        output_path=args.output,
        width=args.width,
        height=args.height,
        style=args.style,
        num_images=args.num,
    )
    
    if success:
        print(f"\n✅ Generación exitosa")
    else:
        print(f"\n❌ Generación falló")
        sys.exit(1)


if __name__ == "__main__":
    main()