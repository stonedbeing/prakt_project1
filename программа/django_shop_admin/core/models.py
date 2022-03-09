from django.db.models import (Model, CharField, TextField, ImageField, 
	BooleanField, PositiveIntegerField, DecimalField, ForeignKey, ManyToManyField,
	CASCADE, CheckConstraint, UniqueConstraint, Q, F)
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
import uuid
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User

# Create your models here.

def shop_image_path_handler(instance, filename):
	return f"{settings.IMAGES_DIR}/shops/{uuid.uuid4()}.{filename.split('.')[-1]}"

class Shop(Model):
	title = CharField(verbose_name='Название', max_length=50, unique=True)
	description = TextField(verbose_name='Описание', null=True, blank=True)
	imageUrl = ImageField(verbose_name="Фото", null=True, blank=True, 
		upload_to=shop_image_path_handler, unique=True)
	product_managers = ManyToManyField(User, limit_choices_to=Q(groups__name='product managers'),
		related_name='managed_shops', verbose_name='Менеджеры продуктов', blank=True)

	def __str__(self):
		return self.title

	class Meta:
		db_table = 'shops'
		verbose_name = "Магазин"
		verbose_name_plural = "Магазины"
		constraints = (
				CheckConstraint(check=Q(title__iregex=r'^\S.*\S$'), name='shop_title_check'),
		)
		
class Category(Model):
	title = CharField(verbose_name='Название', max_length=50, unique=True)
	description = TextField(verbose_name='Описание', null=True, blank=True)
	parents = ManyToManyField('self', symmetrical=False, through='CategoryParent', 
		blank=True, verbose_name='Родительские категории')

	def __str__(self):
		return self.title

	def get_all_paths(self):
		if self.parents:
			for paths, title in ((list(x.get_all_paths()), x.title) for x in self.parents.only('title').order_by('title').iterator()):
				if not paths:
					yield title+' / '
				else:
					for p in paths:
						yield p+title+' / '
		else:
			yield []

	class Meta:
		db_table = 'categories'
		verbose_name = "Категория"
		verbose_name_plural = "Категории"
		constraints = (
				CheckConstraint(check=Q(title__iregex=r'^\S.*\S$'), name='category_title_check'),
		)
		

