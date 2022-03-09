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

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin)
	list_display = ('title','id', 'description')
	search_fields = ('products__id', 'title')
	ordering = ('title',)
	readonly_fields = ('id',)

	def get_fields(self, request, obj=None):
		return ('id', 'title', 'description', 'parents', 'children')
