---
name: template-system
description: HTML infographic templates. Use when creating carousel slides or infographics.
---

# Template System

Instagram post ve carousel icin HTML infographic sablonlari. Playwright ile PNG'ye render edilir.

## 11 Template

| Template | Amac | Kullanim |
|----------|------|----------|
| dashboard-infographic | Panel/dashboard gorunumu | Metrik gosterimi |
| feature-grid-infographic | Grid layout ozellikler | Feature listeleme |
| timeline-infographic | Zaman cizelgesi | Surec/tarihce |
| before-after-infographic | Donusum gosterimi | Karsilastirma |
| comparison-infographic | Yan yana karsilastirma | vs. icerikleri |
| quote-infographic | Alinti/soz | Motivasyon |
| billboard-infographic | Buyuk baslik | Dikkat cekici |
| big-number-infographic | Buyuk sayi/istatistik | %75 gibi rakamlar |
| process-infographic | Adim adim surec | How-to |
| checklist-infographic | Kontrol listesi | Todo/checklist |
| visual-template | Genel sablon | Fallback |

## Rendering

```python
from app.renderer import render_html_to_png, save_html_and_render

# Direkt render
png_path = await render_html_to_png(
    html_content=html_string,
    width=1080,
    height=1080
)

# HTML + PNG kaydet
html_path, png_path = await save_html_and_render(
    html_content=html_string,
    base_name="carousel_slide_1"
)
```

## Boyutlar

| Tip | Boyut | Kullanim |
|-----|-------|----------|
| Instagram Post | 1080x1080 | Kare post |
| Instagram Story | 1080x1920 | Dikey story |
| Carousel Slide | 1080x1080 | Her slide |

## Tasarim Sabitleri (OLIVENET_DESIGN)

### Renkler
```css
/* Ana Renkler */
--olive-900: #1a2e19;  /* Koyu arka plan */
--olive-800: #2d4a2a;
--olive-700: #3d6139;
--olive-600: #4a7c45;  /* Primary */
--olive-500: #5a9654;
--olive-100: #e8f5e6;
--olive-50: #f5faf4;

/* Vurgu */
--sky-500: #38bdf8;    /* Teknoloji mavisi */
--sky-400: #5ecefc;

/* Sektor Renkleri */
--tarim: #2E7D32;      /* Yesil */
--fabrika: #1565C0;    /* Mavi */
--enerji: #F57C00;     /* Turuncu */
```

### Font
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
font-weight: 700; /* Basliklar */
font-weight: 400; /* Body */
```

### Boyutlar
```css
/* Font Sizes */
--h1: 80px;
--h2: 56px;
--h3: 40px;
--body: 32px;
--small: 24px;

/* Border Radius */
--radius-base: 10px;
--radius-card: 16px;
--radius-cta: 24px;
--radius-button: 8px;
```

## Carousel Akisi

```
1. Creator.create_carousel_content(topic)
   -> 5+ slide HTML array

2. Her slide icin:
   render_html_to_png(slide_html)
   -> PNG dosyasi

3. Upload to CDN (imgbb)
   -> Public URL array

4. Instagram carousel API
   -> post_carousel_to_instagram(urls, caption)
```

## Template Data Binding

Her template JSON data alir:

```python
# Dashboard ornegi
data = {
    "title": "IoT Dashboard",
    "subtitle": "Gercek Zamanli Izleme",
    "metrics": [
        {"label": "Sicaklik", "value": "24°C"},
        {"label": "Nem", "value": "65%"}
    ]
}
```

## Dosyalar

- `templates/*.html` - 11 template dosyasi
- `app/renderer.py` - Playwright rendering
- `app/claude_helper.py` - Template generation (generate_*_html fonksiyonlari)
