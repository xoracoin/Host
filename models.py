from django.db import models
from django.conf import settings

NOTIFICATION_TYPES = (
    ('info', 'ℹ️ Ma\'lumot (Moviy)'),
    ('success', '✅ Muvaffaqiyat (Yashil)'),
    ('warning', '⚠️ Ogohlantirish (Sariq)'),
    ('danger', '🚨 Muhim / Xavf (Qizil)'),
)

TARGET_TYPES = (
    ('all', '📢 Barcha foydalanuvchilar (Broadcast)'),
    ('single', '👤 Alohida foydalanuvchiga (Single User)'),
)

class Notification(models.Model):
    title = models.CharField(max_length=200, verbose_name="Sarlavha")
    message = models.TextField(verbose_name="Xabar matni")
    type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='info',
        verbose_name="Xabar turi"
    )
    target_type = models.CharField(
        max_length=20,
        choices=TARGET_TYPES,
        default='all',
        verbose_name="Yuborish qamrovi"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='received_notifications',
        verbose_name="Qabul qiluvchi",
        help_text="Faqat 'Alohida foydalanuvchiga' tanlanganda to'ldiriladi. 'Barchaga' bo'lsa bo'sh qoldiring."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authored_notifications',
        verbose_name="Muallif (Admin)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"
        ordering = ['-created_at']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.target_type == 'single' and not self.recipient:
            raise ValidationError({'recipient': "Alohida foydalanuvchiga yuborish uchun 'Qabul qiluvchi' maydonida foydalanuvchini tanlashingiz shart!"})
        if self.target_type == 'all':
            self.recipient = None

    def __str__(self):
        target_str = "Barchaga" if self.target_type == 'all' else f"{self.recipient.username if self.recipient else 'Noma\'lum'}"
        return f"[{self.get_type_display()}] {self.title} -> {target_str}"

    def is_read_by(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return self.reads.filter(user=user).exists()

    @property
    def reads_count(self) -> int:
        return self.reads.count()

class NotificationRead(models.Model):
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='reads',
        verbose_name="Bildirishnoma"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_reads',
        verbose_name="Foydalanuvchi"
    )
    read_at = models.DateTimeField(auto_now_add=True, verbose_name="O'qilgan vaqt")

    class Meta:
        verbose_name = "O'qilgan bildirishnoma"
        verbose_name_plural = "O'qilgan bildirishnomalar"
        unique_together = ('notification', 'user')
        ordering = ['-read_at']

    def __str__(self):
        return f"{self.user.username} o'qidi: {self.notification.title}"
