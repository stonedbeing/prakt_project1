from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from .models import Shop, Category, Product, ProductImage
from django.db.models import ImageField, Q
from django import forms
from admin_numeric_filter.admin import RangeNumericFilter, NumericFilterModelAdmin
from django.utils.html import format_html
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.db import transaction
from django.contrib.admin.options import (
	PermissionDenied, unquote, DisallowedModelAdminToField,
	flatten_fieldsets, all_valid, IS_POPUP_VAR, TO_FIELD_VAR, 
	helpers, _
)
from django.conf import settings
from django.forms.models import BaseInlineFormSet
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.template.defaultfilters import truncatechars


@admin.register(Product)
class ProductAdmin(NumericFilterModelAdmin):
	list_display = ('title','main_image', 'id', 'amount', 'price', 'active', 'shop_id')
	fieldsets = ((None, {'fields':('id', 'shop', 'title', 'description', 'active', 'amount', 'price')}),
		('КАТЕГОРИИ', {'fields': ('categories',), 'classes': ('collapse',)}),
		('ОСНОВНОЕ ФОТО', {'fields': ('main_image',)}),
		)
	search_fields = ('id', 'title')
	list_filter = ('active',)
	readonly_fields = ('id',)
	filter_horizontal = ('categories',)
	actions = ('make_active', 'make_inactive')
	list_per_page = 50


	def main_image(self, instance):
		url = instance.images.only('image').first()
		if url:
			return format_html("<img src='{}{}' width=100 height=100 style='object-fit:contain' />",
				settings.MEDIA_URL, url.image)
		else:
			return format_html("<img alt='—' />")

	main_image.short_description = 'Фото'

	def formfield_for_manytomany(self, db_field, request, **kwargs):
		if db_field.name == "categories":
			kwargs["queryset"] = Category.objects.only('title').order_by('title')
		return super().formfield_for_manytomany(db_field, request, **kwargs)

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		if db_field.name == 'shop':
			qs = None
			if not request.user.is_superuser:
				qs = request.user.managed_shops
			else:
				qs = Shop.objects
			kwargs['queryset']=qs.only('title').order_by('title')
		return super().formfield_for_foreignkey(db_field, request, **kwargs)
		
	def get_queryset(self, request):
		qs = super().get_queryset(request)
		if request.user.is_superuser:
			return qs
		else:
			return qs.filter(shop__id__in=request.user.managed_shops.values_list('id', flat=True))
			
	@admin.action(description='Сделать активными')
	def make_active(self, request, queryset):
		queryset.update(active=True)

	@admin.action(description='Сделать неактивными')
	def make_inactive(self, request, queryset):
		queryset.update(active=False)
