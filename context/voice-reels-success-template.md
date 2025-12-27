# Voice Reels Başarı Şablonu

Bu şablon, en başarılı voice reels içeriğimizin (ID 104 - Titreşim Analizi) derinlemesine analizinden çıkarılmıştır.

## Performans Benchmark

| Metrik | Başarılı Post (ID 104) | Ortalama | Sektör Ortalaması |
|--------|------------------------|----------|-------------------|
| Reach | 8,949 | 290 | - |
| Saves | 46 | 0.8 | - |
| Shares | 63 | 0 | - |
| Save Rate | 0.51% | 0.26% | 0.1-0.3% |
| Share Rate | 0.70% | 0% | - |
| Engagement | 2.59% | - | 1-3% |

---

## Speech Script Formülü

### Optimum Parametreler
- **Kelime sayısı**: 20-28 kelime (ideal: 25)
- **Karakter sayısı**: 170-200 karakter
- **Cümle sayısı**: 3 cümle (Hook + Açıklama + CTA/Aspirasyon)
- **Ort. kelime/cümle**: 7-9 kelime

### Yapı (3 Cümle Formülü)

```
[HOOK - Soru + Somut Zaman/Rakam]
[AÇIKLAMA - Aktif Fiil + "Sen" Hitabı]
[CTA/ASPİRASYON - Vizyon]
```

### Başarılı Örnek
```
Motorun iki hafta sonra duracağını bilsen ne yapardın?
Titreşim sensörleri anormal sinyalleri yakalar, sen de arızayı beklemeden müdahale edersin.
Kestirimci bakım ile üretim hiç durmasın.
```

### Zorunlu Elementler
- [x] Soru ile başla
- [x] Somut zaman ifadesi ("iki hafta", "3 gün", "24 saat")
- [x] Aktif fiil kullan ("yapardın", "edersin", "kazanırsın")
- [x] "Sen/siz" ile direkt hitap
- [x] Aspirasyonel kapanış

### Kaçınılacaklar
- [ ] 30+ kelime (çok uzun - ID 101 örneği)
- [ ] Pasif cümle yapısı
- [ ] Jargon ağırlıklı dil
- [ ] Emir kipi aşırı kullanımı
- [ ] Marka adını script içinde tekrarlama

---

## Hook Tipi Analizi

### En Etkili Hook: "Senaryo + FOMO"
```
"X olacağını bilsen ne yapardın?"
"X durmadan ÖNCE size haber verse?"
```

### Neden Etkili?
1. Soru formatı → Beyin otomatik cevap arar
2. Somut zaman → Aciliyet hissi yaratır
3. "Bilsen" → Kişiselleştirme
4. Potansiyel kayıp → FOMO tetikler

### Hook Kalıpları (Test Edilecek)
| Kalıp | Örnek | Beklenen Etki |
|-------|-------|---------------|
| Senaryo + Zaman | "X hafta sonra Y olacağını bilsen?" | ⭐⭐⭐⭐⭐ |
| Şok Soru | "Faturaların mı patladı?" | ⭐⭐⭐ |
| Merak | "Gece neler oluyor biliyor musun?" | ⭐⭐⭐ |
| İstatistik | "Her 10 motordan 3'ü..." | ⭐⭐⭐⭐ |

---

## Caption Formülü

### Yapı
```
[EMOJI + HOOK - Soru formatı]

[AÇIKLAMA - 2-3 cümle]

[NASIL ÇALIŞIR - Maddeler (→ ile)]
→ Madde 1
→ Madde 2
→ Madde 3

[MALİYET/DEĞER - Somut karşılaştırma]

[ETKİLEŞİM SORUSU + 👇]

[KAYDET CTA + 📌]

[HASHTAG'LER - 6-10 arası]
```

### Başarılı Caption Örneği
```
⚠️ Motorunuz durmadan 2 HAFTA ÖNCE size haber verse?

Titreşim analizi tam olarak bunu yapıyor. Her motor çalışırken titreşir - ama arıza yaklaştığında bu titreşim değişir.

Nasıl çalışır:
→ Sensörler normal titreşim paternini öğrenir
→ Sapma tespit edildiğinde alarm verir
→ Bakım için zaman kazanırsınız

Beklenmedik duruş maliyeti, planlı bakımın 5-10 katı. Üretim kaybı, acil parça temini, fazla mesai...

Sizin fabrikanızda en kritik motor hangisi? 👇

📌 Kaydet, bakım planlaması yaparken işine yarar!

#Olivenet #KKTC #IoT #EndüstriyelOtomasyon #KestirimciBakım #PredictiveMaintenance #FabrikaOtomasyonu #AkıllıÜretim
```

### Caption Kontrol Listesi
- [x] Hook'ta somut zaman/rakam (2 HAFTA)
- [x] Emoji ile dikkat çekme (⚠️)
- [x] Maddeler (→) ile okunabilirlik
- [x] Somut maliyet karşılaştırması (5-10 kat)
- [x] Etkileşim sorusu + 👇
- [x] Kaydet CTA + 📌
- [x] 6-10 hashtag (dengelenmiş niche + broad)

---

## Video Prompt Formülü

### Sahne Yapısı (6 Saniye)
```
[0-2s] NORMAL DURUM - Makine/sistem normal çalışıyor, LED yeşil
[2-4s] DEĞİŞİM - Bir şey değişiyor, LED amber/sarı oluyor
[4-6s] SONUÇ - Dashboard/alert görünüyor, çözüm gösteriliyor
```

### Teknik Spesifikasyonlar
```yaml
Cinematography:
  Shot: Medium close-up → Close-up
  Movement: Slow dolly in
  Lens: 50mm, shallow depth of field

Lighting:
  Key: Cool industrial LED
  Fill: Warm ambient
  Mood: Professional, technical, slightly dramatic

Palette:
  Primary: Industrial steel gray
  Secondary: Olivenet green (#2E7D32)
  Accent: Warning amber (#FFA726)

Sound:
  Ambient: Industrial hum, machinery
  SFX: Subtle beeps, processing sounds
```

### Video Prompt Template
```
A [SCENE DESCRIPTION] with [KEY VISUAL ELEMENT]. [ENVIRONMENT].

Cinematography:
- Camera shot: [TYPE] transitioning to [TYPE]
- Camera movement: Slow dolly [DIRECTION]
- Lens: 50mm, [DEPTH OF FIELD]

Lighting:
- Key light: [DESCRIPTION]
- Fill: [DESCRIPTION]
- Mood: Professional, technical

Palette:
- Primary: [COLOR]
- Secondary: Olivenet green (#2E7D32)
- Accent: [WARNING/ALERT COLOR]

Actions:
- [0-2s]: [NORMAL STATE]
- [2-4s]: [CHANGE/TRANSITION]
- [4-6s]: [RESOLUTION/ALERT]

Sound:
- Ambient: [ENVIRONMENT SOUND]
- SFX: [ALERT/TECH SOUNDS]
```

---

## Başarı Tahmin Kriterleri

### Yüksek Performans Beklentisi (5+ skor)

| Kriter | Ağırlık | Kontrol |
|--------|---------|---------|
| Hook'ta somut zaman ifadesi | 25% | "X hafta/gün/saat" var mı? |
| Soru ile başlama | 20% | "?" ile bitiyor mu? |
| Aktif fiil kullanımı | 15% | "Sen de...edersin" var mı? |
| Maliyet/değer karşılaştırması | 15% | Somut rakam/oran var mı? |
| Etkileşim sorusu | 10% | 👇 ile soru var mı? |
| Kaydet CTA | 10% | 📌 + "Kaydet" var mı? |
| Optimal uzunluk (20-28 kelime) | 5% | Script uzunluğu uygun mu? |

### Skor Hesaplama
```python
def predict_success(content):
    score = 0
    if "hafta" in content or "gün" in content: score += 25
    if content.strip().split('.')[0].endswith('?'): score += 20
    if "edersin" in content or "yapardın" in content: score += 15
    if any(c.isdigit() for c in content): score += 15
    if "👇" in content: score += 10
    if "Kaydet" in content or "📌" in content: score += 10
    words = len(content.split())
    if 20 <= words <= 28: score += 5
    return score
```

---

## Benzer Yüksek Potansiyelli Konular

"Titreşim Analizi" başarılı olduysa, benzer pattern'e sahip konular:

### Endüstri / Fabrika
1. **Motor Sıcaklık İzleme**: "Motorunuz aşırı ısınmadan 3 GÜN ÖNCE uyarı alın"
2. **Enerji Anomali Tespiti**: "Faturanız patlamadan 1 HAFTA ÖNCE görün"
3. **Kompresör Bakımı**: "Kompresör durmadan 10 GÜN ÖNCE müdahale edin"

### Tarım / Sera
4. **Toprak Nem Kritik**: "Bitkiniz solmadan 2 GÜN ÖNCE sulama alarmı"
5. **Sera Havalandırma**: "Sıcaklık krizi olmadan 4 SAAT ÖNCE müdahale"
6. **Don Uyarısı**: "Don vurmadan 12 SAAT ÖNCE sera kapatma alarmı"

### Genel Pattern
```
"[PROBLEM] olmadan [ZAMAN] ÖNCE [ÇÖZÜM]"
```

---

## A/B Test Önerileri

### Test 1: Hook Karşılaştırması
- **A**: "Motorun 2 hafta sonra duracağını bilsen?" (mevcut)
- **B**: "Her 10 motordan 3'ü beklenmedik arızalanıyor" (istatistik)

### Test 2: CTA Karşılaştırması
- **A**: "📌 Kaydet, bakım planlaması yaparken işine yarar!"
- **B**: "📌 Kaydet ve fabrika müdürüne gönder!"

### Test 3: Süre Karşılaştırması
- **A**: 6 saniye video
- **B**: 10 saniye video (daha fazla detay)

---

## Özet Checklist

Voice Reels oluşturmadan önce kontrol et:

### Speech Script
- [ ] 20-28 kelime arasında mı?
- [ ] Soru ile başlıyor mu?
- [ ] Somut zaman ifadesi var mı?
- [ ] Aktif fiil kullanılıyor mu?
- [ ] "Sen/siz" hitabı var mı?
- [ ] 3 cümle yapısına uyuyor mu?

### Caption
- [ ] Hook'ta emoji + somut zaman var mı?
- [ ] Maddeler (→) ile organize mi?
- [ ] Maliyet/değer karşılaştırması var mı?
- [ ] Etkileşim sorusu + 👇 var mı?
- [ ] Kaydet CTA + 📌 var mı?
- [ ] 6-10 hashtag var mı?

### Video Prompt
- [ ] 3 aşamalı yapı (normal → değişim → sonuç)?
- [ ] Olivenet green (#2E7D32) renk var mı?
- [ ] Slow dolly hareketi belirtildi mi?
- [ ] Ses efektleri tanımlandı mı?

---

*Bu şablon 27 Aralık 2024 tarihinde, ID 104 postunun 8,949 reach ve 46 save performansına dayanarak oluşturulmuştur.*
