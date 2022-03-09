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


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
	list_display = ('title','image','id')
	search_fields = ('title',)
	ordering = ('title',)
	readonly_fields = ('id',)
	filter_horizontal = ('product_managers',)

	def image(self, instance):
		url = instance.imageUrl
		if url:
			return format_html("<img src='{}/{}' width=100 height=100 style='object-fit:contain' />",
				settings.MEDIA_URL, url)
		else:
			return format_html("<img alt='—' />")

	image.short_description = 'Фото'

	def get_fields(self, request, obj=None):
		if request.user.is_superuser:
			return ('id', 'title', 'description', 'imageUrl', 'product_managers')
		else:
			return ('id', 'title', 'description', 'imageUrl')

	def get_queryset(self, request):
		if request.user.is_superuser:
			return super().get_queryset(request)
		else:
			return request.user.managed_shops.order_by(*self.ordering)
