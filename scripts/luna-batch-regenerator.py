#!/usr/bin/env python3
"""
🌙 LUNA Batch Regenerator — Corrige prompts según feedback del Design Critic
y aplica post-procesamiento automático (brillo, contraste, nitidez, overlay de texto).
"""

import os, sys, json, subprocess, time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

# ─── Config ────────────────────────────────────────────────
LUNA_GEN = "/home/polaris/workspace/scripts/luna-gen.py"
OUTPUTS = {
    "padim": "/home/polaris/workspace/luna-padim-output/padim-v3",
    "backbone": "/home/polaris/workspace/luna-backbone-output/backbone-v3",
    "polaris": "/home/polaris/workspace/luna-polaris-output/polaris-v3",
    "visionnorth": "/home/polaris/workspace/luna-visionnorth-output/visionnorth-v3",
}

# ─── Prompts corregidos según Design Critic ────────────────
PROMPTS = {
    "padim": {
        "prompt": "Abstract network of bright connected data nodes, luminous geometric pattern with visible connections, 15% node density, central focal cluster of bright cyan nodes, dark blue background (#0a1628), glowing data paths, visible network structure, clean open source technology aesthetic, well-lit, high contrast, detailed",
        "style": "padim",
        "width": 1200, "height": 630,
        "text_overlay": True,
        "text_config": {
            "headline": "PADIM",
            "subtitle": "Protocolo Abierto de Datos Inmobiliarios",
            "badge": "OPEN STANDARD",
            "color": "#4a8fe7",
        }
    },
    "backbone": {
        "prompt": "Data center server racks with bright glowing blue fiber optic cables, detailed data visualization overlays, luminous server status lights, tech equipment clearly visible, dark navy blue background (#0a0c14), bright cyan and blue accents, clean minimal enterprise aesthetic, well-lit foreground, high detail, 8K sharp",
        "style": "backbone",
        "width": 1200, "height": 630,
        "text_overlay": True,
        "text_config": {
            "headline": "51,969 propiedades.",
            "subtitle": "Una API.",
            "badge": "BACKBONE · API",
            "color": "#0061FE",
        }
    },
    "polaris": {
        "prompt": "Luxury modern house facade with floor-to-ceiling glass walls, infinity pool, golden hour sunset lighting, bright warm illumination, well-lit architecture, visible details, lush tropical landscaping, elevated wide-angle architectural photography, bright and airy, high contrast, 4K sharp, editorial quality",
        "style": "polaris-dfy",
        "width": 1200, "height": 627,
        "text_overlay": True,
        "text_config": {
            "headline": "¿Estás perdiendo leads",
            "subtitle": "porque nadie opera tu marketing?",
            "badge": "POLARIS · AGENCIA DFY",
            "color": "#1EDB7F",
        }
    },
    "visionnorth": {
        "prompt": "Modern SaaS dashboard interface on dark screen, bright glowing green (#0bf47e) and teal (#00b4d8) UI elements, clean data cards, charts and graphs clearly visible, well-lit interface, luminous screen glow, dark mode dashboard, clean minimalist tech aesthetic, bright UI elements, high contrast, detailed",
        "style": "visionnorth",
        "width": 1080, "height": 1080,
        "text_overlay": True,
        "text_config": {
            "headline": "Tu CRM inmobiliario",
            "subtitle": "en 15 minutos",
            "badge": "VISIONNORTH · SaaS",
            "color": "#0bf47e",
        }
    },
}

def post_process(image_path, brightness=1.2, contrast=1.3, sharpness=1.5):
    """Aplica correcciones de brillo, contraste y nitidez"""
    img = Image.open(image_path)
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    return img


def add_text_overlay(img, config):
    """Agrega texto y branding sobre la imagen"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # Parse color
    hex_color = config["color"].lstrip("#")
    color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    # Badge (top-left)
    if "badge" in config:
        try:
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
            draw.text((30, 25), config["badge"], fill=color, font=font_small)
        except: pass
    
    # Headline (center, large)
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        # Semi-transparent background bar for readability
        headline = config["headline"]
        bbox = draw.textbbox((0, 0), headline, font=font_large)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx, ty = (w - tw) // 2, h - 120
        
        # Dark background bar
        bar_h = 100
        bar_y = ty - 10
        for y in range(bar_y, bar_y + bar_h):
            for x in range(0, w):
                px = img.getpixel((x, y)) if y < h else (0,0,0)
                alpha = 0.6
                img.putpixel((x, y), (
                    int(px[0] * (1-alpha)),
                    int(px[1] * (1-alpha)),
                    int(px[2] * (1-alpha))
                ))
        
        draw.text((tx, ty), headline, fill="white", font=font_large)
        
        # Subtitle
        if "subtitle" in config:
            font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
            sub = config["subtitle"]
            bbox2 = draw.textbbox((0, 0), sub, font=font_sub)
            tw2 = bbox2[2] - bbox2[0]
            draw.text(((w - tw2) // 2, ty + 45), sub, fill=(200, 200, 200), font=font_sub)
    except: pass
    
    return img


def generate_and_process(name, config):
    print(f"\n{'='*50}")
    print(f"🎨 {name.upper()}")
    print(f"{'='*50}")
    
    output_base = OUTPUTS[name]
    os.makedirs(os.path.dirname(output_base), exist_ok=True)
    
    # Step 1: Generate with FLUX
    print(f"  1. Generando con FLUX.2 Klein 4B...")
    png_path = f"{output_base}.png"
    
    cmd = [
        sys.executable, LUNA_GEN,
        "--prompt", config["prompt"],
        "--output", png_path,
        "--width", str(config["width"]),
        "--height", str(config["height"]),
        "--style", config["style"],
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not os.path.exists(png_path):
        print(f"  ❌ Error: {result.stderr[:200]}")
        return None
    
    print(f"  ✅ FLUX: {os.path.getsize(png_path)/1024:.0f}KB")
    
    # Step 2: Post-process (brightness, contrast, sharpness)
    print(f"  2. Post-procesando (brillo+contraste+nitidez)...")
    img = post_process(png_path, brightness=1.25, contrast=1.35, sharpness=1.5)
    img.save(png_path, "PNG")
    print(f"  ✅ Post-procesado")
    
    # Step 3: Add text overlay
    if config.get("text_overlay"):
        print(f"  3. Agregando overlay de texto...")
        img = Image.open(png_path)
        img = add_text_overlay(img, config["text_config"])
        img.save(png_path, "PNG")
        print(f"  ✅ Texto añadido")
    
    # Step 4: Convert to WebP
    print(f"  4. Convirtiendo a WebP...")
    webp_path = f"{output_base}.webp"
    img = Image.open(png_path)
    img.save(webp_path, "WEBP", quality=85)
    
    png_size = os.path.getsize(png_path) / 1024
    webp_size = os.path.getsize(webp_path) / 1024
    
    print(f"  ✅ PNG: {png_size:.0f}KB → WebP: {webp_size:.0f}KB")
    print(f"  📐 {img.size[0]}x{img.size[1]}")
    
    return {
        "png": png_path,
        "webp": webp_path,
        "size": img.size,
        "png_kb": png_size,
        "webp_kb": webp_size,
    }


def main():
    print("🌙 LUNA BATCH REGENERATOR")
    print("Regenerando los 4 productos con prompts corregidos + post-procesamiento\n")
    
    results = {}
    for name in ["padim", "backbone", "polaris", "visionnorth"]:
        result = generate_and_process(name, PROMPTS[name])
        if result:
            results[name] = result
    
    print(f"\n{'='*50}")
    print("📊 RESULTADOS")
    print(f"{'='*50}")
    for name, r in results.items():
        print(f"  {name:12s} → {r['webp_kb']:3.0f}KB  {r['size'][0]}x{r['size'][1]}")
    print(f"\n✅ {len(results)}/4 productos regenerados")
    print("⏳ Pendiente: pasar por Design Critic para verificar scores")


if __name__ == "__main__":
    main()