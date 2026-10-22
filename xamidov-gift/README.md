# 🎁 XAMIDOV GIFT — Telegram bot

Telegram Stars, Telegram Premium va sovg'alar bo'yicha buyurtma qabul qiluvchi
to'liq funksional bot. O'zbek tilida ishlaydi (ru/en qo'shish oson).

**Texnologiyalar:** Python 3.11+ · aiogram 3 · SQLite (aiosqlite) · asyncio · python-dotenv

---

## 1. Loyiha tuzilishi

```
xamidov-gift/
├── bot.py                 # botni ishga tushirish
├── config.py              # .env o'qish, admin ID, yo'llar
├── database.py            # SQLite: jadvallar, atomik balans, promo, referal
├── requirements.txt
├── pytest.ini             # test sozlamalari
├── .env.example           # sozlama namunasi
├── .gitignore
├── handlers/              # bo'limlar (routerlar)
│   ├── start.py           # /start, menyu, qo'llanma, yordam, hamkorlik
│   ├── stars.py           # ⭐ Stars + maxsus miqdor (FSM)
│   ├── premium.py         # 💎 Premium tariflari
│   ├── gifts.py           # 🎁 sovg'alar katalogi
│   ├── profile.py         # 👤 kabinet
│   ├── payments.py        # 💳 hisobni to'ldirish + chek + Stars invoice
│   ├── orders.py          # 📦 buyurtmalarim, to'lash, bekor qilish
│   ├── promo.py           # 🎟 promo-kod (foydalanuvchi)
│   ├── referrals.py       # 👥 referal tizimi
│   └── admin.py           # ⚙️ professional admin panel
├── keyboards/
│   ├── main_menu.py       # asosiy Reply menyu
│   ├── inline.py          # barcha inline tugmalar (foydalanuvchi + admin)
│   └── back_kbd.py        # FSM davomidagi «Orqaga» tugmasi
├── services/
│   ├── order_service.py   # buyurtma yaratish/to'lash/holat
│   ├── payment_service.py # chek, tasdiqlash, Telegram Stars invoice
│   └── referral_service.py# referal havola, bonus, statistika
├── utils/
│   ├── logger.py          # log (token yashiriladi)
│   ├── validators.py      # summa/ID/promo tekshiruvi
│   ├── helpers.py         # javob yuborish, adminlarga xabar
│   └── i18n.py            # matnlar (uz; ru/en qo'shish oson)
├── tests/                 # pytest testlari (34 ta)
└── data/                  # baza va log (avtomatik yaratiladi)
```

---

## 2. Ishga tushirish (Windows / PowerShell)

### 2.1. Python bormi tekshirish

```powershell
py -V
```

`Python 3.11` yoki yuqori chiqishi kerak. Yo'q bo'lsa: https://www.python.org/downloads/
(dasturni o'rnatganda **"Add python.exe to PATH"** ni belgilang!)

### 2.2. Papkaga o'tish va virtual muhit yaratish

```powershell
cd "C:\Users\user\Desktop\telegram bot\xamidov-gift"

py -m venv .venv
```

### 2.3. Virtual muhitni yoqish

```powershell
.\.venv\Scripts\Activate.ps1
```

Agar «running scripts is disabled» xatosi chiqsa:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2.4. Kutubxonalarni o'rnatish

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2.5. `.env` faylini sozlash

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` ichida uchta narsa kerak:

| Qiymat | Qayerdan olinadi |
|---|---|
| `BOT_TOKEN` | Telegram'da **@BotFather** → `/newbot` → berilgan token |
| `BOT_USERNAME` | Botingiz username'i, **@ siz** (masalan `xamidov_gift_bot`) |
| `ADMIN_IDS` | Sizning Telegram ID raqamingiz (**@userinfobot** ga yozing) |

Misol:

```
BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BOT_USERNAME=xamidov_gift_bot
ADMIN_IDS=123456789
```

> ⚠️ `.env` faylini hech kim bilan bo'lishmang — u `.gitignore` ichida.

### 2.6. Botni ishga tushirish

```powershell
python bot.py
```

`Bot ishga tushdi: @xamidov_gift_bot` ko'rinsa — hammasi tayyor. ✅
Telegram'da botni `/start` bosib sinab ko'ring.

### 2.7. To'xtatish

Terminalda `Ctrl + C`.

---

## 3. Birinchi marta qilinishi kerak bo'lgan ishlar (admin uchun)

Botga kirib `/admin` yozing va:

1. **⭐/💎/🎁 Mahsulotlar** — narxlarni belgilaring.
   (Boshlang'ich mahsulotlar narxisiz keladi — «narx belgilanmagan» deb chiqadi.
   Buyurtma berish shunda ochilmaydi, xavfsiz.)
2. **💳 To'lov usullari** — «➕ Yangi usul» (masalan UzCard/Click/Payme) va
   rekvizitingizni yozing. Rekvizitni faqat siz berasiz — bot hech qanday
   karta raqamini o'ylab chiqmaydi.
3. **⚙️ Bot sozlamalari** — referal bonus, Stars narxi/kursi, minimal to'ldirish.
4. **🎟 Promo-kodlar** — kerakli bo'lsa kod yarating.

---

## 4. Qanday ishlaydi

**Buyurtma:**
1. Foydalanuvchi bo'limni tanlaydi → mahsulot → «📦 Buyurtma berish».
2. Buyurtma yaratiladi (💳 To'lov kutilmoqda), adminlarga xabar boradi.
3. Foydalanuvchi «💰 Balans bilan to'lash» ni bosadi — pul mablag' yetarli
   bo'lsa balansdan **atomar** ayriladi (bir xato bilan pul yo'qolmaydi).
4. Admin: ⚙️ Bajarilmoqda → ✅ Bajarildi yoki ❌ Rad etish (**pul avtomatik qaytariladi**).

**Hisobni to'ldirish:**
- Usulni tanlash → summa → chek (rasm/PDF/matn) yuborish → admin tasdiqlaydi.
- Bir chek **ikkilan ishlatilmaydi** (maxfiy kalit bilan himoyalangan).
- ⭐ Telegram Stars orqali to'ldirish: Telegram'ning rasmiy to'lovi
  (`pre_checkout_query` + `successful_payment`) ishlatiladi, `charge_id`
  unikalligi bilan pul bir martadan hisoblanadi.

**Yetkazib berish haqida ogohlantirish:**
Telegram API orqali bot **odamga Stars yubora olmaydi** va Premium
rasmiy berib bo'lmaydi — bu qism qo'lda bajariladi. Shuning uchun bot
foydalanuvchiga «avtomatik beriladi» deb yolg'on va'da bermaydi:
buyurtma holati admin bajarishini kutishini ko'rsatadi.

**Referal:**
Bonus taklif qilingan odam **birinchi buyurtma berganda** beriladi — soxta
hisoblar bilan bonus yig'ish qiyinlashtirilgan. O'zini o'zi taklif qilib bo'lmaydi.

---

## 5. Testlar

```powershell
pytest
```

Testlar: balans atomikligi, takroriy chek/to'lov bloklanishi, promo limitlari,
referal bonusi bir martaligi, buyurtma bekor qilinishida pul qaytarilishi.

---

## 6. Muammo chiqsa

| Muammo | Yechim |
|---|---|
| `BOT_TOKEN ... xato` | `.env` dagi token to'g'rimi? Oxirida bo'sh joy yo'qmi? |
| `ADMIN_IDS bo'sh` | `.env` da `ADMIN_IDS=123456789` deb yozing |
| `Activate.ps1` ishlamadi | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `sqlite3.OperationalError` | `data/` papkasiga yozish huquqi bormi? `data/` ni o'chirib qayta ishga tushiring |
| Bot javob bermaydi | `Ctrl+C` bilan to'xtatib `python bot.py` — Internet va token tekshiring |
| Xabar uchun `FloodWrite` | bot avtomatik kechikish bilan yuboradi; qo'lda `broadcast_delay_ms` ni oshiring |
| Log | `data/bot.log` faylini tekshiring (token u yerda yozilmaydi) |

---

## 7. Render'ga chiqarish (cloud, 24/7)

Loyihada tayyor `render.yaml` bor — Render **Blueprint** sifatida o'qiydi.

### 9.1. GitHub'ga yuklash

Render kodni GitHub repodan oladi. Git o'rnatilgan bo'lsa:

```powershell
cd "C:\Users\user\Desktop\telegram bot\xamidov-gift"
git init
git add .
git commit -m "XAMIDOV GIFT bot"
```

Keyin GitHub'da yangi **private** repo yarating va:

```powershell
git remote add origin https://github.com/USERNAME/xamidov-gift.git
git branch -M main
git push -u origin main
```

Git o'rnatilmagan bo'lsa — GitHub.com → *New repository* → *Add file → Upload files*
orqali papkadagi fayllarni brauzer orqali yuklab qo'yasiz (`data/` va `.env` ni
yubormang — ular `.gitignore` da).

### 9.2. Render'da yaratish

1. [render.com](https://render.com) → **New +** → **Blueprint**
2. GitHub repoga ulang → **Connect**
3. `render.yaml` avtomatik tanlanadi → **Apply**
4. Service sahifasida **Environment** bo'limiga kirib qiymatlarni kiriting:

| Qiymat | Qanday qiymat |
|---|---|
| `BOT_TOKEN` | @BotFather dagi token |
| `BOT_USERNAME` | bot username'i (@siz) |
| `ADMIN_IDS` | sizning Telegram ID raqamingiz |

5. **Manual Deploy** → *Deploy latest commit* — kutarish (build) boshlanadi.
6. Logs'da `Bot ishga tushdi: @sizning_bot` ko'rinsa — tayyor! ✅

### 9.3. Bepul plan uchun MUHIM (uyqu masalasi)

Bepul Web Service **15 daqiqadan keyin uxlaysiz** — bot xabarlarni qabul
qilmaydi. Yechim: **UptimeRobot** (bepul) bilan ping qiling:

1. [uptimerobot.com](https://uptimerobot.com) → ro'yxatdan o'ting → *Add New Monitor*
2. Type: **HTTP(s)**, URL: `https://xamidov-gift.onrender.com/health`
3. Interval: **5 yoki 10 minutes** → *Create Monitor*

Bot endi uxlamaydi (birinchi xabar bir necha soniyalik kutarish bilan keladi).

### 9.4. Ma'lumotlar bazasi (SQLite) haqida ogohlantirish ⚠️

Bepul planda **disk yo'q** — qayta deploy/restart bo'lganda `data/xamidov_gift.db`
(to'lovlar, buyurtmalar, foydalanuvchilar) **yo'qolib qoladi**.

To'liq yechim (pulli, lekin arzon — Starter ~$7/oy):

1. Render'da service → **Disk** → **Add Disk** (masalan 1 GB) — mountPath: `/data`
2. Environment'da qo'shing: `DB_PATH=/data/xamidov_gift.db`
3. `render.yaml` dagi **(B) PUL REJIM** blokidagi worker+disk variantini yoqing
   (`type: web` → `type: worker`, `healthCheckPath` ni o'chiring).

Worker rejimda bot **hech qachon uxlamaydi** va baza diskda saqlanadi.

### 9.5. Render'da xatolik chiqsa

| Alomat | Yechim |
|---|---|
| Build xatosi: `No module named ...` | `requirements.txt` to'g'rimi? |
| `Sozlama xatosi: BOT_TOKEN` | Environment'da qiymat kiritilmagan yoki bo'sh qatorlar bor |
| Bot ishga tushdi lekin javob bermaydi | UptimeRobot ping qo'shing (9.3) |
| Baza "yo'qoldi" | 9.4 — disk qo'shing |
| Logs'ni ko'rish | Service → **Logs** tugmasi |

---

## 8. Xavfsizlik

- Token faqat `.env` da, kodga yozilmagan.
- Admin buyruqlari faqat `.env` dagi ID lar uchun; admin harakatlari
  `admin_logs` jadvaliga yoziladi.
- Balans o'zgarishi faqat atomik tranzaksiya orqali; xatoda hammasi bekor bo'ladi.
- Bir to'lov / chek / Telegram charge ikki marta hisoblanmaydi.
- Foydalanuvchi faqat o'z buyurtmalarini ko'ra oladi.

---

## 9. Tillar (ru/en qo'shish)

`utils/i18n.py` dagi `TEXTS` lug'atiga `ru` va `en` qatorlarini qo'shing —
butun kod o'zgarmaydi. Foydalanuvchi tili `users.lang` ustunida saqlanadi.
