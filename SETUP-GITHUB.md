# 🚀 راهنمای راه‌اندازی GitHub Actions

## مراحل راه‌اندازی:

### 1. ساخت Repository در GitHub
1. به https://github.com/new بروید
2. نام repo را **dollar-price-bot** بگذارید
3. **Public** انتخاب کنید (برای رایگان بودن)
4. **Create repository** بزنید

### 2. آپلود فایل‌ها
در ترمینال این دستورات را اجرا کنید:

```bash
cd "F:\freebuff projects"

# ساخت Git repo
git init
git add dollar-checker-cloud.py .github/workflows/dollar-checker.yml
git commit -m "Initial commit - dollar price checker"

# اتصال به GitHub (نام کاربری خود را جایگزین کنید)
git remote add origin https://github.com/YOUR_USERNAME/dollar-price-bot.git
git branch -M main
git push -u origin main
```

### 3. تنظیم Secrets در GitHub
1. به صفحه repo در GitHub بروید
2. **Settings** → **Secrets and variables** → **Actions**
3. روی **New repository secret** کلیک کنید و دو مورد اضافه کنید:

| Name | Value |
|------|-------|
| `TELEGRAM_TOKEN` | `7902915191:AAFi7N7WZB-dD5IXQo6IqoVBaEM8RBv7erE` |
| `TELEGRAM_CHANNEL` | `@robomohsen` |

### 4. فعال‌سازی GitHub Actions
1. به تب **Actions** در repo بروید
2. روی **I understand my workflows, go ahead and enable them** کلیک کنید
3. workflow هر ساعت به صورت خودکار اجرا می‌شود!

### 5. تست دستی
1. در تب Actions، روی **Dollar Price Checker** کلیک کنید
2. روی **Run workflow** بزنید
3. پیام در کانال تلگرام ارسال می‌شود!

## ✅ مزایا:
- **رایگان:** ۲۰۰۰ دقیقه رایگان در ماه (کافی برای هر ساعت)
- **خودکار:** ۲۴ ساعته، ۷ روز هفته
- **بدون سرور:** نیازی به VPS یا کامپیوتر روشن نیست
- **قابل اعتماد:** GitHub 99.9% uptime دارد

## 📱 نتیجه:
هر ساعت یک پست در کانال **@robomohsen** با قیمت‌های لحظه‌ای بازار آزاد ارسال می‌شود:
- 💵 دلار
- 🥇 طلا و انس
- 🪙 سکه
- ₿ بیتکوین و تتر
- 📈 شاخص بورس
