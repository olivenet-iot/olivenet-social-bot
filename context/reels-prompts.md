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

## VEO 3.1 PROMPT FORMATI

### Timestamp Yapısı (8 saniye):
```
[00:00-00:02] [HOOK] [Shot tipi], [subject], [dramatic action]. Audio: [impact sound].
[00:02-00:04] [CONTEXT] [Camera movement], [subject detail], [environment]. Ambient: [atmosphere].
[00:04-00:06] [DEVELOPMENT] [Transition], [new angle], [key visual]. SFX: [subtle effect].
[00:06-00:08] [RESOLUTION] [Final shot], [emotional moment], [closing visual]. Music: [mood].
```

### 5-Part Formula:
[CINEMATOGRAPHY] + [SUBJECT] + [ACTION] + [CONTEXT] + [STYLE]

### Kamera Hareketleri (Veo 3.1):
| Hareket | Prompt Terimi | Kullanım |
|---------|--------------|----------|
| Dolly | smooth dolly in/out | Yaklaşma/uzaklaşma |
| Crane | crane shot rising/descending | Yükseklik değişimi |
| Orbit | 180° arc around subject | Ürün etrafında dönme |
| Tracking | lateral tracking shot | Yatay takip |
| Rack focus | rack focus from A to B | Odak geçişi |
| Handheld | subtle handheld movement | Organik his |

### Audio Entegrasyonu:
- Her shot için ses tanımı ekle
- Audio: Impact sesleri (beep, click, whoosh)
- Ambient: Ortam sesleri (ventilation, nature, city)
- SFX: Spesifik efektler
- Music: Duygu tonu (hopeful, dramatic, calm)

### Veo 3.1 Örnek Prompt (8s):
```
[00:00-00:02] Medium close-up, IoT sensor device on industrial shelf, LED indicator
suddenly activates with green pulse. Audio: subtle electronic beep.

[00:02-00:04] Smooth dolly out reveals greenhouse environment, sensor connected to
irrigation system, morning light through glass panels. Ambient: gentle ventilation hum.

[00:04-00:06] Rack focus transition to water droplets on plant leaves, automated
sprinkler activating precisely. SFX: soft water spray sound.

[00:06-00:08] Wide establishing shot, thriving greenhouse with multiple sensor nodes
glowing green, camera slowly rises with crane movement. Music: hopeful ambient tone.
```

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

---

## KLING AI PROMPT FORMATI

### Temel Formül
```
Subject + Description + Movement + Scene + Camera + Lighting + Atmosphere
```

### Bileşenler

| Bileşen | Açıklama | Örnek |
|---------|----------|-------|
| Subject | Ana odak | A technician, A sensor device |
| Description | Görünüm detayları | wearing safety helmet, in blue uniform |
| Movement | Hareket durumu | checking the screen, walking slowly |
| Scene | Ortam | industrial factory floor |
| Camera | Kamera teknikleri | medium shot, bokeh background |
| Lighting | Işık durumu | ambient lighting, morning light |
| Atmosphere | Genel hava | professional mood, cinematic feel |

### Kling Kuralları
- Basit, virgülle ayrılmış cümleler
- 5-10 saniye içerik (Veo/Sora'dan uzun!)
- Fiziksel karmaşıklıktan kaçın (top sektirme vb.)
- Sayılardan kaçın ("10 sensör" → "multiple sensors")
- Max 200 karakter önerilir

### Kling Prompt Örnekleri

**Basit:**
```
A technician checking a digital screen in a factory, industrial lighting.
```

**Detaylı:**
```
Medium shot, bokeh background, a technician wearing safety helmet and blue uniform, examining a glowing sensor device mounted on industrial pipes, factory interior with steel structures, warm industrial lighting with lens flare, cinematic color grading, professional documentary mood.
```

### IoT/Olivenet Şablonları (Kling)

**Fabrika/Enerji:**
```
[Camera], [Subject] in [clothing], [action] in [location], [background], [lighting], [atmosphere].
```
Örnek:
```
Medium shot with shallow depth of field, an engineer in safety vest, monitoring energy meters on a control panel, industrial facility with pipes and gauges in background, warm ambient lighting, professional documentary style.
```

**Sera/Tarım:**
```
Slow tracking shot, modern irrigation sensors among green crops, water droplets on leaves, greenhouse interior, soft morning sunlight, fresh technological atmosphere.
```

**Akıllı Bina:**
```
Close-up with rack focus, a smart thermostat displaying temperature, mounted on modern office wall, minimalist interior with glass partitions, soft diffused lighting, clean technological aesthetic.
```

### Camera Language (Kling)

| Türkçe | İngilizce Prompt |
|--------|------------------|
| Yakın çekim | Close-up, extreme close-up |
| Orta çekim | Medium shot |
| Geniş çekim | Wide shot, establishing shot |
| Alçak açı | Low-angle shot |
| Yüksek açı | High-angle shot |
| Arka plan bulanık | Bokeh background, shallow depth of field |
| Takip | Tracking shot, following shot |
| Dönen kamera | Circling camera, orbit shot |

### Lighting (Kling)

| Türkçe | İngilizce Prompt |
|--------|------------------|
| Doğal ışık | Natural lighting, ambient light |
| Sabah ışığı | Morning light, golden hour |
| Endüstriyel | Industrial lighting, fluorescent |
| Dramatik | Dramatic lighting, chiaroscuro |
| Yumuşak | Soft diffused lighting |
| Lens parlaması | Lens flare |
