# Olivenet Görsel Tasarım Rehberi

## Sosyal Medya Görseli Özellikleri

**Standart Boyut:** 1080x1080px (Instagram/Facebook kare)
**Alternatif:** 1200x628px (LinkedIn/Twitter yatay)

---

## Renk Paleti

### Ana Renk: Olive (Zeytin Yeşili)

| Ton | HEX Kodu | Kullanım |
|-----|----------|----------|
| Olive 900 | `#1a2e1a` | En koyu arka plan, metin |
| Olive 800 | `#243524` | Koyu arka plan |
| Olive 700 | `#2d4a2d` | Primary button, ana vurgu |
| Olive 600 | `#3a5f3a` | Hover durumları |
| Olive 500 | `#4a7c4a` | Ana marka rengi, ikonlar |
| Olive 400 | `#5e9a5e` | Vurgu elementleri |
| Olive 300 | `#7ab87a` | Açık vurgular |
| Olive 200 | `#a3d4a3` | Hafif arka planlar |
| Olive 100 | `#d1e8d1` | Çok açık arka plan |
| Olive 50 | `#e8f4e8` | En açık arka plan |

### Vurgu Rengi: Sky (Gökyüzü Mavisi)

| Ton | HEX Kodu | Kullanım |
|-----|----------|----------|
| Sky 500 | `#0ea5e9` | Teknoloji vurgusu |
| Sky 400 | `#38bdf8` | Açık vurgu |
| Sky 300 | `#7dd3fc` | Hafif vurgu |

### Sektörel Renkler

| Sektör | Renk | HEX Kodu |
|--------|------|----------|
| Tarım/Sera | Emerald | `#10b981` |
| Enerji | Amber | `#f59e0b` |
| Kestirimci Bakım | Violet | `#8b5cf6` |
| Bina/Tesis | Sky | `#0ea5e9` |

### Nötr Renkler

| Kullanım | Açık Tema | Koyu Tema |
|----------|-----------|-----------|
| Arka Plan | `#ffffff` | `#0a0a0a` |
| Kart Arka Plan | `#ffffff` | `#171717` |
| Metin (Ana) | `#0a0a0a` | `#fafafa` |
| Metin (İkincil) | `#737373` | `#a3a3a3` |
| Border | `#e5e5e5` | `rgba(255,255,255,0.1)` |

### Chart Renkleri (Grafikler)

| Sıra | HEX Kodu |
|------|----------|
| Chart 1 | `#4a7c4a` (Olive) |
| Chart 2 | `#0ea5e9` (Sky) |
| Chart 3 | `#22c55e` (Green) |
| Chart 4 | `#f59e0b` (Amber) |
| Chart 5 | `#8b5cf6` (Violet) |

---

## Gradient Kullanımı

### Ana Arka Plan Gradient (Koyu Tema)
```css
background: linear-gradient(to bottom right, rgba(26,46,26,0.4), #0a0a0a);
```

### Metin Gradient
```css
background: linear-gradient(to right, #4a7c4a, #0ea5e9);
-webkit-background-clip: text;
color: transparent;
```

### Sektörel Dashboard Gradient'leri

**Tarım:**
```css
background: linear-gradient(to bottom right, rgba(6,78,59,0.4), rgba(6,78,59,0.6));
border-color: rgba(16,185,129,0.2);
```

**Enerji:**
```css
background: linear-gradient(to bottom right, rgba(120,53,15,0.4), rgba(120,53,15,0.6));
border-color: rgba(245,158,11,0.2);
```

**Kestirimci Bakım:**
```css
background: linear-gradient(to bottom right, rgba(76,29,149,0.4), rgba(76,29,149,0.6));
border-color: rgba(139,92,246,0.2);
```

**Bina:**
```css
background: linear-gradient(to bottom right, rgba(12,74,110,0.4), rgba(12,74,110,0.6));
border-color: rgba(14,165,233,0.2);
```

### CTA Banner Gradient
```css
background: linear-gradient(to bottom right, #365314, #1a2e1a);
/* olive-700 to olive-900 */
```

---

## Glassmorphism (Cam Efekti)

### Açık Tema Glass
```css
.glass {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}
```

### Koyu Tema Glass
```css
.glass-dark {
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
```

### Metrik Kart Glass
```css
.metric-card {
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  padding: 12px;
}
```

---

## Tipografi

### Font Ailesi
- **Ana Font:** Geist Sans (system-ui benzeri, clean modern)
- **Mono Font:** Geist Mono (kod ve sayılar için)

### Font Boyutları

| Element | Mobil | Desktop | Weight |
|---------|-------|---------|--------|
| H1 | 36px | 48-60px | Bold (700) |
| H2 | 30px | 36-48px | Bold (700) |
| H3 | 20px | 24-30px | Semibold (600) |
| H4 | 18px | 20-24px | Semibold (600) |
| Body | 16px | 18px | Normal (400) |
| Small | 14px | 14px | Normal (400) |
| Caption | 12px | 12px | Medium (500) |

### Sosyal Medya İçin Önerilen

| Element | Boyut | Weight |
|---------|-------|--------|
| Ana Başlık | 48-64px | Bold |
| Alt Başlık | 24-32px | Semibold |
| Açıklama | 18-24px | Normal |
| Stat Rakamı | 56-72px | Bold |
| Stat Etiketi | 16-20px | Normal |

---

## Kart Tasarımı

### Standart Kart
```css
.card {
  background: var(--card); /* #ffffff veya #171717 */
  border: 1px solid var(--border);
  border-radius: 16px; /* rounded-2xl */
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.card:hover {
  border-color: rgba(74, 124, 74, 0.5);
  box-shadow: 0 10px 25px rgba(74, 124, 74, 0.05);
}
```

### İkon Container
```css
.icon-container {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: rgba(74, 124, 74, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-container svg {
  width: 24px;
  height: 24px;
  color: #4a7c4a;
}
```

---

## Buton Stilleri

### Primary Button
```css
.btn-primary {
  background: #4a7c4a;
  color: #ffffff;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 500;
}

.btn-primary:hover {
  background: #3a5f3a;
}
```

### Outline Button
```css
.btn-outline {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--foreground);
  padding: 12px 24px;
  border-radius: 8px;
}

.btn-outline:hover {
  border-color: rgba(74, 124, 74, 0.3);
}
```

---

## Animasyon Pattern'leri

### Fade In Up
```css
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fade-in-up {
  animation: fadeInUp 0.5s ease-out;
}
```

### Pulse (Canlı Gösterge)
```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.pulse {
  animation: pulse 2s infinite;
}
```

### Float (Dekoratif Elementler)
```css
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.float {
  animation: float 4s ease-in-out infinite;
}
```

---

## Dashboard Mockup Elementleri

### Metrik Kutusu
```html
<div class="metric-box">
  <div class="metric-icon">
    <!-- SVG Icon -->
  </div>
  <div class="metric-label">Toprak Nem</div>
  <div class="metric-value">54%</div>
</div>
```

```css
.metric-box {
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  padding: 12px;
}

.metric-label {
  font-size: 12px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 4px;
}

.metric-value {
  font-size: 20px;
  font-weight: 600;
  color: #38bdf8; /* veya sektörel renk */
}
```

### Mini Bar Chart
```css
.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 48px;
}

.bar {
  flex: 1;
  background: rgba(74, 124, 74, 0.4);
  border-radius: 4px 4px 0 0;
}
```

### Toggle Switch
```css
.switch {
  width: 40px;
  height: 20px;
  border-radius: 10px;
  background: #4a7c4a;
  position: relative;
}

.switch-knob {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  position: absolute;
  right: 2px;
  top: 2px;
}
```

### Circular Gauge (Sağlık Skoru)
```html
<svg viewBox="0 0 96 96">
  <circle cx="48" cy="48" r="40" fill="none" stroke="#1a2e1a" stroke-width="8"/>
  <circle cx="48" cy="48" r="40" fill="none" stroke="#4a7c4a" stroke-width="8"
          stroke-dasharray="251.2" stroke-dashoffset="50" stroke-linecap="round"
          transform="rotate(-90 48 48)"/>
</svg>
```

---

## Dekoratif Elementler

### Grid Pattern (Arka Plan)
```css
.grid-pattern {
  background-image:
    linear-gradient(to right, rgba(74,124,74,0.1) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(74,124,74,0.1) 1px, transparent 1px);
  background-size: 64px 64px;
}
```

### Glowing Orb
```css
.glow-orb {
  position: absolute;
  width: 384px;
  height: 384px;
  background: rgba(74, 124, 74, 0.2);
  border-radius: 50%;
  filter: blur(48px);
  animation: pulse 4s infinite;
}
```

### Corner Dots
```css
.corner-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(74, 124, 74, 0.5);
  position: absolute;
}

.corner-dot.top-left { top: 12px; left: 12px; }
.corner-dot.top-right { top: 12px; right: 12px; background: rgba(14,165,233,0.5); }
.corner-dot.bottom-left { bottom: 12px; left: 12px; }
.corner-dot.bottom-right { bottom: 12px; right: 12px; }
```

---

## Progress Bar

```css
.progress-bar {
  height: 8px;
  background: rgba(74, 124, 74, 0.2);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(to right, #4a7c4a, #5e9a5e);
  border-radius: 4px;
}
```

---

## Sosyal Medya Görseli Şablonu Yapısı

```
+--------------------------------------------------+
|  [Grid Pattern Arka Plan]                        |
|                                                  |
|  +--------------------------------------------+  |
|  |  [Glassmorphism Ana Kart]                  |  |
|  |                                            |  |
|  |  [Icon]  [Başlık]                          |  |
|  |                                            |  |
|  |  +----------------+  +----------------+    |  |
|  |  | Metrik Kutusu  |  | Metrik Kutusu  |    |  |
|  |  +----------------+  +----------------+    |  |
|  |                                            |  |
|  |  [Ana Stat]                                |  |
|  |  XX%                                       |  |
|  |  [Stat Etiketi]                            |  |
|  |                                            |  |
|  +--------------------------------------------+  |
|                                                  |
|  [Logo]                    [Hashtag]             |
|                                                  |
+--------------------------------------------------+
```

---

## Önemli Notlar

1. **Koyu tema tercih edilmeli** - Dashboard ve teknoloji görselleri için
2. **Glassmorphism kullanımı** - Modern ve premium görünüm için
3. **Gradient'ler yumuşak olmalı** - Olive tonlarında
4. **Dekoratif noktalar** - Köşelerde küçük renkli noktalar
5. **Grid pattern** - Arka planda hafif grid deseni
6. **Animasyon izlenimi** - Statik görsellerde "canlılık" hissi veren elementler
