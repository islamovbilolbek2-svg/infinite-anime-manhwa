# Infinite Anime/Manhwa — backend (Flask + SQLite)

## 1. Birinchi marta ishga tushirish (kompyuteringizda)

Python 3.10+ o'rnatilgan bo'lishi kerak (python.org dan).
Papka ichida terminal oching (VS Code: Terminal → New Terminal):

    pip install -r requirements.txt
    python app.py

Brauzerda oching: http://127.0.0.1:5000
Admin panel:      http://127.0.0.1:5000/admin
Standart parol:   infinite2026   (INTERNETGA CHIQARISHDAN OLDIN ALBATTA O'ZGARTIRING)

Parolni o'zgartirish (Windows PowerShell):

    $env:ADMIN_PASSWORD="o'zingizning-kuchli-parolingiz"
    python app.py

## 2. Kontent qo'shish

1. /admin ga kiring
2. "+ Yangi hikoya" — nom, turi (Anime yoki Manhwa), tavsif, janrlar, muqova
3. Hikoya kartasidagi "+ Qism" (anime) yoki "+ Bob" (manhwa):
   - Anime: YouTube havolasi (Unlisted video) YOKI mp4/webm fayl
   - Manhwa: bobning barcha sahifa rasmlarini birdan tanlang
     (fayl nomi bo'yicha tartiblanadi: 1.jpg, 2.jpg, 10.jpg)
4. Bo'ldi — bosh sahifa, ro'yxatlar, qidiruv, o'qish/tomosha sahifalari avtomatik yangilanadi.

## 3. Bosh sahifadagi scroll-fon rasmlari

static/images/ papkasiga scene1.jpg, scene2.jpg, scene3.jpg ni qo'ying.

## 4. Fayllar tuzilishi

    app.py               — butun backend (marshrutlar, baza, admin, xavfsizlik)
    templates/           — HTML shablonlar (Jinja2)
    templates/admin/     — admin panel sahifalari
    static/css/style.css — dizayn
    static/uploads/      — yuklangan muqova, sahifa va video fayllar
    site.db              — ma'lumotlar bazasi (birinchi ishga tushirishda o'zi yaratiladi)

## 5. Muhim

- site.db va static/uploads/ — sizning BUTUN kontentingiz. Muntazam zaxira (backup) nusxasini oling.
- Internetga chiqarishda `python app.py` emas, `gunicorn app:app` ishlatiladi.
  Hosting tanlashda yuklangan fayllar va site.db DOIMIY saqlanadigan joy (persistent disk) kerak.
- ADMIN_PASSWORD va SECRET_KEY ni hosting sozlamalarida (environment variables) bering.
