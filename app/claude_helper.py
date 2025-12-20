"""
Olivenet Social Media Bot - Claude Code Helper
Claude Code CLI wrapper for AI-powered content generation.
"""
import asyncio
import logging
import re
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

async def run_claude_code(prompt: str, timeout: int = 60) -> str:
    """
    Run Claude Code CLI with the given prompt.

    Args:
        prompt: The prompt to send to Claude Code
        timeout: Maximum execution time in seconds

    Returns:
        Claude's response as a string

    Raises:
        Exception: If timeout occurs or Claude Code fails
    """
    try:
        process = await asyncio.create_subprocess_exec(
            'claude', '-p', prompt, '--print',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(settings.base_dir)
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8').strip()
            logger.error(f"Claude Code error: {error_msg}")
            raise Exception(f"Claude Code failed: {error_msg}")

        result = stdout.decode('utf-8').strip()
        logger.info(f"Claude Code response received ({len(result)} chars)")
        return result

    except asyncio.TimeoutError:
        if process:
            process.kill()
        logger.error(f"Claude Code timeout after {timeout}s")
        raise Exception(f"Claude Code timeout ({timeout}s)")
    except FileNotFoundError:
        logger.error("Claude Code CLI not found")
        raise Exception("Claude Code CLI not found. Is it installed?")

async def generate_post_text(topic: str) -> str:
    """
    Generate social media post text using Claude Code.
    Uses social media expert analysis for better engagement.

    Args:
        topic: The topic/subject for the post

    Returns:
        Generated post text in Turkish
    """
    prompt = f"""
/opt/olivenet-social-bot/context/ klasorundeki TUM dosyalari oku:
- company-profile.md (sirket bilgileri)
- content-strategy.md (icerik stratejisi)
- social-media-expert.md (sosyal medya uzmanligi - ONEMLI!)

## GOREV: Sosyal Medya Uzmani Olarak Dusun

Konu: {topic}

### ADIM 1: ANALIZ (icinden gec)
Once sunlari dusun:
- Bu konu KKTC'deki hedef kitleyi neden ilgilendirsin?
- Hangi duygusal tetikleyici en etkili olur? (FOMO, korku, umut, merak)
- Hook nasil olmali? (Soru, istatistik, sok edici bilgi?)
- Sosyal medya expert rehberindeki basari faktorlerinden hangileri uygulanabilir?

### ADIM 2: POST URET
Analiz sonucuna gore Facebook postu yaz:

Kurallar:
- Ilk cumle HOOK olmali (scroll durdurucu)
- Turkce, samimi ama profesyonel ton
- Maksimum 3-4 kisa paragraf
- Emoji kullan ama abartma (3-5 emoji)
- Somut fayda veya rakam icersin
- CTA (call-to-action) ekle
- Hashtag'ler ekle (#Olivenet #KKTC + konuya ozel 2-3 tane)

### ADIM 3: KENDINI DEGERLENDIR
Post'u urettikten sonra kontrol et:
- Hook Test: Ilk cumle dikkat cekiyor mu?
- Deger Test: Okuyucu ne kazaniyor?
- KKTC Test: Yerel isletme sahibi ilgilenir mi?

Eger herhangi bir test basarisizsa, post'u revize et.

### CIKTI
SADECE final post metnini yaz.
Analiz veya degerlendirme notlarini YAZMA.
"""

    logger.info(f"Generating post text for topic: {topic}")
    result = await run_claude_code(prompt, timeout=settings.claude_timeout_post)

    # Clean up any potential markdown artifacts
    result = clean_response(result)

    return result

async def suggest_topics() -> dict:
    """
    Generate topic suggestions like a social media expert.
    Considers current season and day of week.

    Returns:
        Dictionary with topics list: {"topics": [{"title": ..., "reason": ..., "hook": ..., "engagement": ...}, ...]}
    """
    import json
    from datetime import datetime

    today = datetime.now()
    day_names = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
    day_name = day_names[today.weekday()]
    month = today.month

    # Determine season
    if month in [12, 1, 2]:
        season = "kis"
        season_themes = "enerji tasarrufu, isitma maliyetleri, kis bakimi"
    elif month in [3, 4, 5]:
        season = "ilkbahar"
        season_themes = "ekim donemi, sera hazirligi, yeni sezon"
    elif month in [6, 7, 8]:
        season = "yaz"
        season_themes = "su tasarrufu, sera sogutma, yuksek sicaklik"
    else:
        season = "sonbahar"
        season_themes = "hasat donemi, verim analizi, kis hazirligi"

    prompt = f"""
/opt/olivenet-social-bot/context/social-media-expert.md dosyasini oku.
/opt/olivenet-social-bot/context/company-profile.md dosyasini oku.

## GOREV: Sosyal Medya Stratejisti Olarak Konu Oner

Bugun: {day_name}
Mevsim: {season}
Mevsimsel temalar: {season_themes}

Olivenet icin bugun paylasilabilecek 3 farkli post konusu oner.

Oneriler farkli kategorilerden olsun:
- Biri egitici/bilgilendirici
- Biri duygusal/hikaye
- Biri pratik ipucu

## KRITIK: JSON FORMATI
SADECE asagidaki JSON formatinda cevap ver, baska bir sey YAZMA:

{{"topics": [
  {{"title": "Konu basligi kisa", "reason": "Neden bugun 1 cumle", "hook": "Hook onerisi ilk cumle", "engagement": "yuksek"}},
  {{"title": "Ikinci konu", "reason": "Neden", "hook": "Hook", "engagement": "orta"}},
  {{"title": "Ucuncu konu", "reason": "Neden", "hook": "Hook", "engagement": "yuksek"}}
]}}

SADECE JSON yaz, markdown code block (```) KULLANMA!
"""

    logger.info("Generating topic suggestions")
    result = await run_claude_code(prompt, timeout=60)
    result = clean_response(result)

    # Parse JSON response
    try:
        # Remove any markdown artifacts
        result = result.strip()
        if result.startswith('```'):
            result = result.split('\n', 1)[1]
        if result.endswith('```'):
            result = result.rsplit('```', 1)[0]
        result = result.strip()

        data = json.loads(result)
        logger.info(f"Parsed {len(data.get('topics', []))} topic suggestions")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse topic suggestions JSON: {e}")
        # Return a fallback structure
        return {
            "topics": [
                {"title": "IoT ile Enerji Tasarrufu", "reason": "Kis mevsiminde enerji maliyetleri artar", "hook": "Elektrik faturanizi %30 dusurmenin sirri", "engagement": "yuksek"},
                {"title": "Akilli Sera Otomasyonu", "reason": "Teknoloji ilgi ceker", "hook": "Seraniz siz uyurken bile calissin!", "engagement": "orta"},
                {"title": "KKTC'de Dijital Donusum", "reason": "Yerel baglam onemli", "hook": "Kibris'ta isletmenizi nasil dijitallestirirsiniz?", "engagement": "yuksek"}
            ],
            "error": "JSON parse failed, using fallback"
        }

async def generate_visual_html(post_text: str, topic: str) -> str:
    """
    Generate HTML code for social media visual using Claude Code.

    Args:
        post_text: The post text to create a visual for
        topic: The topic/subject for context

    Returns:
        Complete HTML code for the visual (1080x1080px)
    """
    # Truncate post text if too long to avoid prompt issues
    short_post = post_text[:500] if len(post_text) > 500 else post_text

    # Logo base64 verisini oku
    try:
        from app.logo_data import LOGO_BASE64
        logo_img = LOGO_BASE64.strip()
    except Exception:
        logo_img = ""

    prompt = f"""
/opt/olivenet-social-bot/context/visual-guidelines.md dosyasini oku.

Bu post icin 1080x1080px sosyal medya gorseli HTML'i olustur:

Post metni: {short_post[:300]}
Konu: {topic}

## TASARIM KURALLARI:

0. FONT (zorunlu):
   - External font KULLANMA (Google Fonts, vb.)
   - System font kullan: font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
   - Ya da: font-family: system-ui, sans-serif;

1. RENK PALETİ (zorunlu):
   - Arka plan: Koyu gradient (#0a0a0a, #1a2e1a)
   - Ana vurgu: Olive yeşil (#4a7c4a)
   - Accent: Sky mavi (#0ea5e9) veya Violet (#8b5cf6)
   - Metin: Beyaz ve gri tonları

2. STİL:
   - Glassmorphism kartlar (backdrop-filter: blur)
   - Köşelerde dekoratif renkli noktalar
   - Grid pattern arka plan (opsiyonel)
   - Modern, minimal, profesyonel

3. SOL ALT KÖŞE - LOGO (zorunlu):
   - Bu base64 logo resmini kullan: {{{{logo}}}}
   - Logo ve yazı yan yana olacak:
   ```
   <div style="position:absolute;bottom:24px;left:24px;display:flex;align-items:center;gap:12px;">
     <img src="{{{{logo}}}}" style="width:48px;height:48px;border-radius:8px;">
     <span style="color:#ffffff;font-size:24px;font-weight:600;font-family:system-ui,sans-serif;">Olivenet</span>
   </div>
   ```

4. SAĞ ALT KÖŞE:
   - Hashtag YAZMA (bunlar post metninde olacak)
   - Boş bırak veya minimal dekoratif element

5. YARATICILIK (önemli):
   - Her görsel farklı layout dene
   - Bazen tek büyük metrik, bazen grid
   - Bazen ilustrasyon/ikon ağırlıklı, bazen data-driven
   - Sıkıcı ve tekrarlayan olma
   - Konuya özel yaratıcı elementler ekle:
     * Tarım: yaprak, damla, toprak ikonları
     * Enerji: şimşek, güneş, pil ikonları
     * Kestirimci bakım: dişli, grafik, kalp atışı
     * Bina: ev, termometre, hava ikonları
   - SVG ikonlar kullanabilirsin (inline)

6. İÇERİK:
   - Dikkat çekici başlık
   - 1-2 anahtar metrik/istatistik
   - Konuyla ilgili görsel element

SADECE HTML kodunu yaz. Markdown code block (```) KULLANMA.
Aciklama yazma, direkt <!DOCTYPE html> ile basla.
HTML icinde {{{{logo}}}} placeholder'i kullan, ben degistirecegim.
"""

    logger.info(f"Generating visual HTML for topic: {topic}")
    result = await run_claude_code(prompt, timeout=settings.claude_timeout_visual)

    # Clean up and extract HTML
    result = extract_html(result)

    # Logo placeholder'ı gerçek base64 ile değiştir
    if logo_img and "{{logo}}" in result:
        result = result.replace("{{logo}}", logo_img)

    return result

def clean_response(text: str) -> str:
    """Remove markdown artifacts and clean up response."""
    # Remove code blocks if present
    text = re.sub(r'^```\w*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n?```$', '', text, flags=re.MULTILINE)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text

def extract_html(text: str) -> str:
    """Extract HTML content from response, handling various formats."""
    text = text.strip()

    # Remove markdown code blocks if present
    if text.startswith('```'):
        # Find the end of the opening tag
        first_newline = text.find('\n')
        if first_newline != -1:
            text = text[first_newline + 1:]
        # Remove closing ```
        if text.endswith('```'):
            text = text[:-3]

    text = text.strip()

    # Ensure it starts with DOCTYPE or html tag
    if not text.lower().startswith('<!doctype') and not text.lower().startswith('<html'):
        # Try to find HTML content
        html_match = re.search(r'(<!DOCTYPE html>.*</html>)', text, re.IGNORECASE | re.DOTALL)
        if html_match:
            text = html_match.group(1)
        else:
            # Wrap in basic HTML structure
            text = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Olivenet Social</title>
</head>
<body>
{text}
</body>
</html>"""

    return text

async def improve_post_text(original_post: str, feedback: str) -> str:
    """
    Improve an existing post based on feedback.

    Args:
        original_post: The original post text
        feedback: User feedback for improvement

    Returns:
        Improved post text
    """
    prompt = f"""
Asagidaki sosyal medya postunu gelistir.

Mevcut post:
{original_post}

Geri bildirim/istek:
{feedback}

Kurallari koru:
- Turkce
- Emoji kullan (abartma)
- Hashtag'ler olsun
- CTA ekle

SADECE yeni post metnini yaz, aciklama yapma.
"""

    logger.info("Improving post text based on feedback")
    result = await run_claude_code(prompt, timeout=settings.claude_timeout_post)
    return clean_response(result)

async def generate_visual_html_with_feedback(post_text: str, topic: str, feedback: str) -> str:
    """
    Generate HTML code for social media visual with user feedback.

    Args:
        post_text: The post text to create a visual for
        topic: The topic/subject for context
        feedback: User feedback for visual modification

    Returns:
        Complete HTML code for the visual (1080x1080px)
    """
    short_post = post_text[:500] if len(post_text) > 500 else post_text

    try:
        from app.logo_data import LOGO_BASE64
        logo_img = LOGO_BASE64.strip()
    except Exception:
        logo_img = ""

    prompt = f"""
/opt/olivenet-social-bot/context/visual-guidelines.md dosyasini oku.

Bu post icin 1080x1080px sosyal medya gorseli HTML'i olustur:

Post metni: {short_post[:300]}
Konu: {topic}

KULLANICI GERI BILDIRIMI (ONCELIKLI - MUTLAKA UYGULA):
{feedback}

## TASARIM KURALLARI:

0. FONT (zorunlu):
   - System font kullan: font-family: system-ui, sans-serif;

1. RENK PALETI:
   - Arka plan: Koyu gradient (#0a0a0a, #1a2e1a)
   - Ana vurgu: Olive yesil (#4a7c4a)
   - Accent: Sky mavi (#0ea5e9) veya Violet (#8b5cf6)

2. STIL:
   - Glassmorphism kartlar
   - Modern, minimal, profesyonel
   - Cok fazla metin KOYMA - ozet ve gorsel agirlikli

3. SOL ALT KOSE - LOGO:
   <div style="position:absolute;bottom:24px;left:24px;display:flex;align-items:center;gap:12px;">
     <img src="{{{{logo}}}}" style="width:48px;height:48px;border-radius:8px;">
     <span style="color:#ffffff;font-size:24px;font-weight:600;">Olivenet</span>
   </div>

4. SAG ALT KOSE: Bos birak (hashtag yok)

5. YARATICILIK:
   - Her gorsel farkli layout dene
   - Sikici ve tekrarlayan olma

SADECE HTML kodunu yaz. Markdown code block (```) KULLANMA.
Aciklama yazma, direkt <!DOCTYPE html> ile basla.
HTML icinde {{{{logo}}}} placeholder'i kullan.
"""

    logger.info(f"Generating visual HTML with feedback for topic: {topic}")
    result = await run_claude_code(prompt, timeout=120)

    result = extract_html(result)

    if logo_img and "{{logo}}" in result:
        result = result.replace("{{logo}}", logo_img)

    return result


async def generate_video_prompt(post_text: str, topic: str) -> str:
    """
    Claude Code ile Veo 3 için profesyonel video prompt'u üret.

    Args:
        post_text: Türkçe post metni
        topic: Konu

    Returns:
        İngilizce video prompt
    """
    short_post = post_text[:400] if len(post_text) > 400 else post_text

    prompt = f"""
## GÖREV: Veo 3 Video Prompt Mühendisliği

Post metni (Türkçe): {short_post}
Konu: {topic}

Sen bir profesyonel video prompt mühendisisin. Google Veo 3 için mükemmel bir video prompt'u yazacaksın.

### VEO 3 PROMPT KURALLARI:

1. **DİL**: Mutlaka İNGİLİZCE yaz

2. **YAPI** (Bu sırayla):
   - Kamera hareketi (örn: "Slow cinematic dolly shot", "Aerial drone view")
   - Ana sahne açıklaması
   - Işıklandırma (örn: "soft natural lighting", "cool blue tech lighting")
   - Renk paleti (Olivenet: olive green #4a7c4a, sky blue #38bdf8)
   - Atmosfer/mood
   - Detaylar ve aksiyon

3. **OLIVENET MARKA KİMLİĞİ**:
   - Renk paleti: Olive green ve sky blue tonları
   - Profesyonel ama samimi
   - Teknoloji + doğa birleşimi
   - Modern, temiz, minimal

4. **KONUYA GÖRE GÖRSEL TEMALAR**:

   AKILLI TARIM / SERA:
   - Yeşil seralar, bitkiler, damla sulama
   - Sensörler toprakta/yapraklarda
   - Güneş ışığı, doğal ortam
   - Su damlacıkları, büyüme

   ENERJİ İZLEME:
   - Elektrik sayaçları, LED göstergeler
   - Veri akışı görselleştirmesi
   - Fabrika/tesis ortamı
   - Dashboard ekranlar

   KESTİRİMCİ BAKIM:
   - Endüstriyel makineler, dişliler
   - Sensörler, kablolar
   - Diagnostik ekranlar

   BİNA OTOMASYONU:
   - Modern ofis/bina içi
   - Akıllı termostatlar, ışık kontrol

5. **TEKNİK DETAYLAR**:
   - 5 saniyelik video için yeterli hareket
   - Çok karmaşık sahneler YAPMA
   - Tek bir güçlü görsel konsept
   - Tek sürekli sahne

6. **YASAKLAR**:
   - Metin/yazı içerme
   - Logo gösterme
   - İnsan yüzü close-up
   - Çok hızlı kamera hareketi

### ÖRNEK İYİ PROMPTLAR:

Tarım:
"Slow cinematic tracking shot through a modern greenhouse, rows of healthy green plants with small IoT sensors attached to soil, morning sunlight streaming through glass panels creating soft shadows, water droplets on leaves glistening, color palette of olive green and soft earth tones, peaceful and technological atmosphere"

Enerji:
"Smooth dolly shot revealing a wall of digital energy meters with blue LED displays showing real-time data, soft industrial lighting, data visualization particles flowing between meters, olive green and sky blue accent colors, professional corporate environment"

### ŞİMDİ PROMPT YAZ:

Yukarıdaki kurallara uyarak, verilen post için TEK bir İngilizce video prompt yaz.
Sadece prompt'u yaz, başka açıklama yapma. Tırnak işareti kullanma.
"""

    logger.info(f"Generating video prompt for topic: {topic}")
    result = await run_claude_code(prompt, timeout=90)

    # Temizle
    result = result.strip()

    # Tırnak işaretlerini kaldır
    if result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    if result.startswith("'") and result.endswith("'"):
        result = result[1:-1]

    logger.info(f"Video prompt generated: {result[:100]}...")
    return result


async def generate_flux_prompt(post_text: str, topic: str) -> str:
    """
    Claude Code ile FLUX.2 Pro için optimize edilmiş prompt üret.

    Args:
        post_text: Türkçe post metni
        topic: Konu

    Returns:
        İngilizce FLUX prompt
    """
    short_post = post_text[:400] if len(post_text) > 400 else post_text

    prompt = f"""
/opt/olivenet-social-bot/context/flux-prompting-guide.md dosyasını oku.
/opt/olivenet-social-bot/context/company-profile.md dosyasını oku.

## GÖREV: FLUX.2 Pro için Profesyonel Görsel Prompt'u

Post metni (Türkçe): {short_post}
Konu: {topic}

### FLUX PROMPT KURALLARI:

1. **DİL**: Mutlaka İNGİLİZCE yaz

2. **FRAMEWORK**: Subject + Action + Style + Context
   - En önemli elementler BAŞTA
   - 40-80 kelime arası ideal

3. **OLIVENET MARKA KİMLİĞİ**:
   - Renkler: olive green (#4a7c4a), sky blue (#38bdf8)
   - Profesyonel, modern, teknolojik
   - Temiz, minimal estetik

4. **KONUYA GÖRE GÖRSEL TEMALAR**:

   AKILLI TARIM / SERA:
   - Modern sera, yeşil bitkiler, IoT sensörler
   - Doğal güneş ışığı, soft shadows
   - Toprak nem sensörleri, damla sulama
   - "commercial agriculture photography style"

   ENERJİ İZLEME:
   - Dijital enerji sayaçları, LED göstergeler
   - Endüstriyel tesis ortamı
   - Data visualization, dashboard ekranları
   - "professional industrial photography"

   KESTİRİMCİ BAKIM:
   - CNC makineler, endüstriyel ekipman
   - Vibrasyon sensörleri, diagnostik ekranlar
   - Mühendis tablet ile çalışıyor
   - "corporate industrial photography style"

   BİNA OTOMASYONU:
   - Modern ofis, akıllı termostat
   - Cam, çelik, minimal mimari
   - Konfor ve teknoloji birleşimi
   - "architectural interior photography"

5. **TEKNİK DETAYLAR**:
   - 1024x1024 kare format için kompozisyon
   - Shallow depth of field (f/2.8)
   - Soft, professional lighting
   - Clean background

6. **ÖRNEK PROMPT YAPISI**:
   "[Ana konu detaylı], [aksiyon/durum], [ortam], [ışık], olive green (#4a7c4a) and sky blue (#38bdf8) accent colors, [stil], [teknik], [atmosfer]"

7. **YASAKLAR**:
   - Negatif prompt KULLANMA
   - "Olivenet" yazısı EKLEME (sonra ekleriz)
   - Çok karmaşık sahne YAPMA

### ŞİMDİ PROMPT YAZ:

Yukarıdaki kurallara uyarak, verilen post için TEK bir İngilizce görsel prompt yaz.
Sadece prompt'u yaz, başka açıklama yapma.
"""

    logger.info(f"Generating FLUX prompt for topic: {topic}")
    result = await run_claude_code(prompt, timeout=90)

    # Temizle
    result = result.strip()
    if result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    if result.startswith("'") and result.endswith("'"):
        result = result[1:-1]

    logger.info(f"FLUX prompt generated: {result[:100]}...")
    return result
