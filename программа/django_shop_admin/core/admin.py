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

class ManagedShopsInlineAdmin(admin.TabularInline):
	model = Shop.product_managers.through
	extra = 0
	verbose_name_plural = 'Связанные магазины'
	verbose_name = 'Магазин'
	
class CustomUserAdmin(UserAdmin):
	def get_inlines(self, request, obj):
		if obj and (obj.managed_shops or obj.groups.filter(name='product managers').exists()):
			return (ManagedShopsInlineAdmin,)
		else:
			return ()

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

class ShortDescriptionListFieldMixin:
	short_description_length = 160

	def short_description(self, instance):
		return truncatechars(instance.description, self.short_description_length)

	short_description.short_description = 'Описание'


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin, ShortDescriptionListFieldMixin):
	list_display = ('title','image','id', 'short_description')
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
			
	def can_access_object(self, request, obj):
		if obj is None:
			return True
		return request.user.managed_shops.filter(id=obj.id).exists()

	def has_view_permission(self, request, obj=None):
		if request.user.is_superuser:
			return True
		else:
			if super().has_view_permission(request, obj):
				return self.can_access_object(request, obj)
			else:
				return False

class ParentCategoryFilter(admin.SimpleListFilter):
	title = 'Род. категория'
	parameter_name = 'parents__id'

	def lookups(self, request, model_admin):
		objs = Category.objects.filter(from_category__isnull=False).only('title').distinct().order_by('title')
		return [(o.pk, o.title) for o in objs]

	def queryset(self, request, queryset):
		value = self.value()
		if value is not None:
			return queryset.filter(parents__id=self.value())
		return queryset


class CategoryAdminForm(forms.ModelForm):
	parents = forms.ModelMultipleChoiceField(label='Родительские категории',
				queryset = Category.objects.only('title').order_by('title'),
				required=False,
				widget=FilteredSelectMultiple(
						verbose_name='Родительские категории',
						is_stacked=False
					))

	children = forms.ModelMultipleChoiceField(label='Дочерние категории',
				queryset=Category.objects.only('title').order_by('title'),
				required=False,
				widget=FilteredSelectMultipleWithReadonlyMode(
						verbose_name='Дочерние категории',
						is_stacked=False
					)
				)

	class Meta:
		model = Category
		fields = '__all__'

	def __init__(self, *args, **kwargs):
		super(CategoryAdminForm, self).__init__(*args, **kwargs)
		instance = kwargs.get("instance")
		if instance and instance.pk:
			self.fields['parents'].queryset=Category.objects.filter(
						~(Q(pk=instance.pk)|Q(pk__in=instance.category_set.values('id')))
						).only('title').order_by('title')
			self.fields['parents'].initial=instance.parents.all()
			self.fields['children'].queryset=Category.objects.filter(
							~(Q(pk=instance.pk)|Q(pk__in=instance.parents.values('id')))
					).only('title').order_by('title')
			self.fields['children'].initial=instance.category_set.all()
			self.fields['children'].widget.attrs['readonly']=True

	def save(self, commit=True):
		category = super(CategoryAdminForm, self).save(commit=False)
		if commit:
			error=1
			try:
				with transaction.atomic():
					category.save()
					data = self.cleaned_data['parents']
					if self.fields['parents'].has_changed(self.fields['parents'].initial, data):
						category.parents.set(data)
					error=2
					data = self.cleaned_data['children']
					if self.fields['children'].has_changed(self.fields['children'].initial, data):
						category.category_set.set(data)
			except forms.ValidationError as e:
				self.add_error('parents' if error==1 else 'children', e)
			except Exception as e:
				self.add_error(None, e)
		return category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin)
	list_display = ('title','id', 'description', 'category_actions')
	search_fields = ('products__id', 'title')
	list_filter = (ParentCategoryFilter,)
	ordering = ('title',)
	readonly_fields = ('id',)
	form = CategoryAdminForm

	def get_fields(self, request, obj=None):
		return ('id', 'title', 'description', 'parents', 'children')
		
	def get_urls(self):
		urls = super().get_urls()
		custom_urls = [
			path(
				'<int:category_id>/paths/',
				self.admin_site.admin_view(self.process_paths),
				name='category-paths',
			),
		]
		return custom_urls + urls    

	def category_actions(self, obj):
		return format_html(
			'<a class="button" href="{}">Показать пути</a>',
			reverse('admin:category-paths', args=[obj.pk])
		)

	category_actions.short_description = 'Действия'
	category_actions.allow_tags = True

	def process_paths(self, request, category_id, *args, **kwargs):
		obj = self.get_object(request, category_id)
		context = self.admin_site.each_context(request)
		context['opts'] = self.model._meta
		paths = list(obj.get_all_paths())
		context['paths'] = paths
		context['title'] = f'Пути к категории {obj.title} ({len(paths)})'        
		return TemplateResponse(
			request,
			'admin/category_paths.html',
			context,
		)
		

class ShopFilter(admin.SimpleListFilter):
	title = 'Магазин'
	parameter_name = 'shop__id'

	def lookups(self, request, model_admin):
		objs = Shop.objects if request.user.is_superuser else request.user.managed_shops
		objs = objs.filter(products__isnull=False).only('title').distinct().order_by('title')
		return [(o.pk, o.title) for o in objs]

	def queryset(self, request, queryset):
		value = self.value()
		if value is not None:
			return queryset.filter(shop__id=self.value())
		return queryset


class CategoryFilter(admin.SimpleListFilter):
	title = 'Категория'
	parameter_name = 'categories__id'

	def lookups(self, request, model_admin):
		filters = {'products__isnull': False}
		if not request.user.is_superuser:
			filters['products__shop__id__in']=request.user.managed_shops.values_list('id', flat=True)
		objs = Category.objects.filter(**filters).only('title').distinct().order_by('title')
		return [(o.pk, o.title) for o in objs]

	def queryset(self, request, queryset):
		value = self.value()
		if value is not None:
			return queryset.filter(categories__id=self.value())
		return queryset


@admin.register(Product)
class ProductAdmin(NumericFilterModelAdmin):
	list_display = ('title','main_image', 'id', 'amount', 'price', 'active', 'shop_id')
	fieldsets = ((None, {'fields':('id', 'shop', 'title', 'description', 'active', 'amount', 'price')}),
		('КАТЕГОРИИ', {'fields': ('categories',), 'classes': ('collapse',)}),
		('ОСНОВНОЕ ФОТО', {'fields': ('main_image',)}),
		)
	search_fields = ('id', 'title')
	list_filter = ('active',CategoryFilter,ShopFilter)
	readonly_fields = ('id',)
	filter_horizontal = ('categories',)
	actions = ('make_active', 'make_inactive')
	list_per_page = 50
	
	class Media:
		css = {'all': ('css/productlist.css',)}


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
