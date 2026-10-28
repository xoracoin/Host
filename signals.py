from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, UserQuota

@receiver(post_save, sender=User)
def create_user_quota(sender, instance, created, **kwargs):
    if created:
        from apps.adminpanel.models import SystemSetting
        settings_obj = SystemSetting.get_settings()
        UserQuota.objects.get_or_create(
            user=instance,
            defaults={
                'max_disk_mb': settings_obj.default_disk_mb,
                'max_running_bots': settings_obj.default_max_bots
            }
        )
