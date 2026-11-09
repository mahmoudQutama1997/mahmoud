# إعادة نشر وصلني على Render بالخطة المجانية

## تنبيه قبل الرفع
- لا تحذف قاعدة بيانات PostgreSQL الحالية ولا تنشئ قاعدة جديدة.
- لا تضع DATABASE_URL أو كلمة المرور داخل ملفات GitHub أو هذا الملف.
- هذا المشروع يستخدم قاعدة بيانات واحدة مشتركة لكل البوابات.

## إعداد خدمة Render الحالية (بدون Pre-Deploy مدفوع)
اترك Root Directory فارغاً، ثم اضبط:

**Build Command**
```bash
pip install -r backend/requirements.txt
```

**Start Command**
```bash
cd backend && python manage.py migrate --noinput && daphne -b 0.0.0.0 -p $PORT config.asgi:application
```

الأمر يشغّل migrations عند بدء الخدمة ثم يشغّل Daphne. لا تحتاج إلى Pre-Deploy Command؛ اتركه فارغاً.

## Environment Variables
في Render > Environment تأكد من وجود:
- `DATABASE_URL`: Internal Database URL لقاعدة PostgreSQL الحالية (لا تنشره).
- `SECRET_KEY`: قيمة سرية قوية.
- `DEBUG=False`
- `ALLOWED_HOSTS=waselni-backend1997.onrender.com`
- `CORS_ALLOWED_ORIGINS`: أضف كل نطاقات Vercel المستخدمة، مفصولة بفواصل وبدون `/` في النهاية. لا تمسح النطاقات الأخرى التي ما زالت مستخدمة.

## واجهات Vercel
انشر كل واجهة من مجلد `frontend` أو من إعدادات المشروع الموجودة، مع `VITE_API_URL=https://waselni-backend1997.onrender.com/api`. لا تنشئ Backend منفصلاً لكل واجهة.

## بعد النشر
افتح Render Logs وتأكد أن سجل التشغيل يعرض تطبيق migrations بنجاح ثم بدء Daphne. إذا ظهر خطأ migration، أوقف التعديلات وأرسل أول رسالة خطأ كاملة؛ لا تحذف الجداول أو قاعدة البيانات.
