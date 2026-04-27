import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile

logger = logging.getLogger('accounts')


@receiver(post_save, sender=User)
def create_or_save_profile(sender, instance, created, **kwargs):
    """
    Kullanıcı oluşturulduğunda profil oluştur,
    güncellendiğinde mevcut profili kaydet.

    DÜZELTME: Önceden iki ayrı @receiver vardı.
    İkinci receiver (save_profile) AttributeError verebiliyordu
    çünkü yeni kullanıcı kaydında profile henüz oluşmamış olabilir.
    Tek receiver'da birleştirildi ve güvenli hale getirildi.
    """
    if created:
        Profile.objects.get_or_create(user=instance)
        logger.info(f'Yeni profil oluşturuldu: {instance.username}')
    else:
        try:
            instance.profile.save()
        except Profile.DoesNotExist:
            Profile.objects.create(user=instance)
            logger.warning(f'Profil eksikti, yeniden oluşturuldu: {instance.username}')
