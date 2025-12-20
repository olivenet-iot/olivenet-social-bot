# Instagram Reels - Professional Video Prompting Guide

## Optimal Reels Specifications
- Aspect Ratio: 9:16 (dikey/vertical)
- Resolution: 720x1280 veya 1080x1920
- Duration: 5-8 saniye ideal
- Format: MP4, H.264, AAC audio

## Model Seçim Kriterleri

| Complexity | Model | Kullanım |
|------------|-------|----------|
| LOW | Veo 3 | Tek sahne, statik/basit hareket, ürün odaklı |
| MEDIUM | Sora 2 | 2-3 element, kamera takibi, orta hareket |
| HIGH | Sora 2 Pro | Dönüşüm, çoklu sahne, insan figürü |

---

## SORA 2 PROMPT FORMATI

### Temel Yapı:
```
[SCENE DESCRIPTION - Detaylı sahne tanımı]

Cinematography:
- Camera shot: [wide/medium/close-up]
- Camera movement: [static/dolly/pan/arc/reveal]
- Lens: [35mm/50mm/85mm] + depth of field

Lighting:
- Key light: [ana ışık kaynağı ve yönü]
- Fill: [dolgu ışık]
- Mood: [professional/warm/dramatic/calm]

Palette:
- [Primary color - Olivenet green #2E7D32]
- [Secondary color - Sky blue #38bdf8]
- [Accent color]

Actions:
- [0-2s]: Hook aksiyonu
- [2-4s]: Ana aksiyon
- [4-6s]: Kapanış

Sound:
- Ambient: [ortam sesi]
- SFX: [efektler]
```

---

## VEO 3 PROMPT FORMATI

### Timestamp Yapısı:
```
[00:00-00:02] [Shot tipi], [subject], [action]. Ambient: [ses].
[00:02-00:04] [Shot tipi], [subject], [action]. SFX: [efekt].
[00:04-00:06] [Shot tipi], [final görüntü]. Emotion: [duygu].
```

### 5-Part Formula:
[CINEMATOGRAPHY] + [SUBJECT] + [ACTION] + [CONTEXT] + [STYLE]

Örnek:
"Slow dolly shot, IoT sensor device on greenhouse shelf, LED indicator blinking green, 
morning sunlight through glass panels, professional documentary style, shallow depth of field"

---

## OLIVENET İÇERİK ŞABLONLARI

### 1. Teknoloji/Ürün Tanıtım
```
A sleek IoT sensor device sits on a modern surface. Camera performs slow 180-degree arc 
around the device. Holographic data visualizations materialize showing temperature and 
humidity readings. Clean white background with subtle olive green accent lighting.

Camera: Medium close-up, slow orbital arc
Lighting: Soft diffused from above-left, blue LED edge glow
Mood: Premium, technological, trustworthy
Palette: White (#FFFFFF), Olive green (#2E7D32), Tech blue (#1976D2)
```

### 2. Sera/Tarım Sahnesi
```
Morning sunlight streams through greenhouse glass panels. Rows of healthy green plants 
with small sensors between them. Camera tracks smoothly along plant rows, shallow depth 
of field keeps focus on nearest sensor showing green status light.

Camera: Wide establishing, then tracking medium shot
Lighting: Natural morning light, soft volumetric rays
Mood: Peaceful, hopeful, natural
Sound: Gentle ventilation hum, distant bird chirps
```

### 3. Data Visualization
```
Dark background with bold 3D animated text forming from digital particles. Numbers 
and graphs animate and float in space. Camera slowly rotates around the composition.
Cool blue and green color palette with subtle glow effects.

Camera: Static center, slow rotation
Style: Clean motion graphics, minimal
Palette: Dark (#1a1a1a), Olive (#2E7D32), Blue (#38bdf8)
```

### 4. Before/After Transformation
```
Split screen comparison: Left side shows struggling plants with harsh lighting,
right side shows thriving greenhouse with sensors and soft natural light.
Animated wipe transition moves from left to right, transforming the scene.

Camera: Static center frame
Transition: Horizontal wipe reveal
Contrast: Harsh vs soft lighting, dying vs thriving
```

---

## KAMERA HAREKETLERİ

| Hareket | Kullanım | Etki |
|---------|----------|------|
| Static | Ürün odaklı | Profesyonel, güvenilir |
| Slow dolly in | Reveal, dikkat çekme | Merak, ilgi |
| Slow dolly out | Büyük resim | Bağlam, anlam |
| Pan (yatay) | Geniş sahne tarama | Keşif |
| Arc (orbital) | Ürün etrafında | Premium, 3D etki |
| Reveal | Arkadan öne | Sürpriz, wow |

---

## IŞIK AYARLARI

### Sabah/Doğal
- Golden hour quality
- Soft shadows
- Warm tones

### Stüdyo/Ürün
- Key light: 45° yukarıdan
- Fill: %50 yoğunluk
- Rim light: arkadan ayrıştırma

### Dramatik/Tech
- Single strong source
- Deep shadows
- Blue/green accent

---

## OLIVENET MARKA RENKLERİ

| Renk | Hex | Kullanım |
|------|-----|----------|
| Olive Green | #2E7D32 | Ana marka, doğa |
| Sky Blue | #38bdf8 | Teknoloji, data |
| White | #FFFFFF | Temiz, modern |
| Dark Gray | #1a1a1a | Arka plan, kontrast |

---

## YASAKLAR (Guardrails)

- Gerçek insan yüzleri (kalite sorunları)
- Hızlı kesimler (tek sahne tercih)
- Yazı/metin overlay (post-production'da ekle)
- Kompleks multi-scene (basit tut)
- Belirsiz tanımlamalar ("güzel bir şey" yerine spesifik ol)

---

## CAPTION KURALLARI (Instagram)

- Max 100 kelime
- Hook ile başla
- 3 posttan 1'inde soft CTA
- 6-8 hashtag
- Sabit: #Olivenet #KKTC #IoT

---

## PROMPT KALİTE KONTROL LİSTESİ

- [ ] Shot tipi belirtildi mi? (wide/medium/close-up)
- [ ] Kamera hareketi tanımlandı mı?
- [ ] Işık kaynağı ve yönü var mı?
- [ ] 3-5 renk palette tanımlı mı?
- [ ] Aksiyon beat'leri zamanlanmış mı?
- [ ] Ses/ambient tanımı var mı?
- [ ] 9:16 aspect ratio belirtildi mi?
- [ ] Süre 5-8 saniye arasında mı?
